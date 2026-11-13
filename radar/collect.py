"""The collector: discover new repos, snapshot star counts, record Trending.

GitHub keeps no public star history, so growth can only be measured by
counting stars ourselves at regular intervals. Each run:

1. Discover  - search for repos created in the last DISCOVERY_DAYS days that
               already have MIN_STARS stars, one query per creation day.
2. Benchmark - read github.com/trending and record what it shows. This is the
               baseline the radar has to beat.
3. Refresh   - fetch current counts for every watched repo the search did not
               return (older repos, repos found on Trending).
4. Store     - one snapshot file, new registry lines, one run summary line.

A failed step does not stop the run: whatever was collected is still stored,
the problem is written to the run summary, and the exit code is 1.

The query asks only for cheap fields. Measured on 13 Nov 2026, a page of 100
search results takes about 3 seconds with these fields and 6-10 seconds once
topics and open-issue counts are added. Those details are fetched later, and
only for the few repos that turn out to be interesting.
"""

from __future__ import annotations

import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from . import github, store

DISCOVERY_DAYS = 30
MIN_STARS = 10
PAGE_SIZE = 100
SEARCH_RESULT_CAP = 1000  # GitHub returns at most 1,000 results per search query
WORKERS = 4  # a few parallel calls; far below GitHub's concurrency limits
PAUSE_SECONDS = 0.25

REPO_FRAGMENT = """
fragment RepoFields on Repository {
  id
  nameWithOwner
  stargazerCount
  forkCount
  createdAt
  pushedAt
  isFork
  isArchived
  description
  primaryLanguage { name }
  licenseInfo { spdxId }
}
"""

SEARCH_QUERY = REPO_FRAGMENT + """
query Search($q: String!, $after: String) {
  search(query: $q, type: REPOSITORY, first: 100, after: $after) {
    repositoryCount
    pageInfo { hasNextPage endCursor }
    nodes { ...RepoFields }
  }
  rateLimit { cost remaining resetAt }
}
"""

NODES_QUERY = REPO_FRAGMENT + """
query Nodes($ids: [ID!]!) {
  nodes(ids: $ids) { ...RepoFields }
  rateLimit { cost remaining resetAt }
}
"""

REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ARTICLE = re.compile(r'<article class="Box-row">(.*?)</article>', re.S)
_HEADING_LINK = re.compile(r'<h2 class="h3 lh-condensed">\s*<a[^>]*?href="/([^"]+)"', re.S)
_STARS_TODAY = re.compile(r"([\d,]+)\s+stars?\s+today")

Gql = Callable[[str, dict[str, Any]], tuple[dict[str, Any], list[dict[str, Any]]]]


@dataclass
class RunReport:
    started_at: str
    discovered: int = 0
    new_repos: int = 0
    refreshed: int = 0
    gone: int = 0
    snapshot_rows: int = 0
    snapshot_file: str = ""
    trending_rows: int = 0
    truncated_days: list[str] = field(default_factory=list)
    api_calls: int = 0
    rate_cost: int = 0
    rate_remaining: int | None = None
    errors: list[str] = field(default_factory=list)
    finished_at: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class Fetched:
    """What one worker brought back. Workers never touch the shared report."""

    repos: list[dict[str, Any]] = field(default_factory=list)
    gone: list[str] = field(default_factory=list)
    total: int = 0
    calls: int = 0
    cost: int = 0
    remaining: int | None = None
    errors: list[str] = field(default_factory=list)

    def note(self, data: dict[str, Any]) -> None:
        rate = data.get("rateLimit") or {}
        self.calls += 1
        self.cost += rate.get("cost", 0)
        if rate.get("remaining") is not None:
            self.remaining = rate["remaining"]


def _merge(report: RunReport, fetched: Fetched) -> None:
    report.api_calls += fetched.calls
    report.rate_cost += fetched.cost
    if fetched.remaining is not None:
        known = report.rate_remaining
        report.rate_remaining = fetched.remaining if known is None else min(known, fetched.remaining)
    report.errors.extend(fetched.errors)


def _describe(error: Exception) -> str:
    return str(error) if isinstance(error, github.GitHubError) else f"{type(error).__name__}: {error}"


def _keep_valid(nodes: list[Any], out: "Fetched", label: str) -> None:
    """Normalize what can be normalized; one malformed node must not lose the page."""
    for node in nodes or []:
        if not node or not node.get("id"):
            continue
        try:
            out.repos.append(normalize(node))
        except (KeyError, TypeError, AttributeError) as error:
            out.errors.append(f"{label}: unexpected repo shape ({_describe(error)})")


def normalize(node: dict[str, Any]) -> dict[str, Any]:
    """Flatten one GraphQL repository node into the shape the store uses."""
    return {
        "id": node["id"],
        "name": node["nameWithOwner"],
        "stars": node["stargazerCount"],
        "forks": node["forkCount"],
        "created_at": node["createdAt"],
        "pushed_at": node.get("pushedAt"),
        "fork": node["isFork"],
        "archived": node["isArchived"],
        "description": node.get("description"),
        "language": (node.get("primaryLanguage") or {}).get("name"),
        "license": (node.get("licenseInfo") or {}).get("spdxId"),
    }


def snapshot_row(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": repo["id"],
        "stars": repo["stars"],
        "forks": repo["forks"],
        "pushed_at": repo["pushed_at"],
    }


def registry_row(repo: dict[str, Any], first_seen: str, source: str) -> dict[str, Any]:
    return {
        "id": repo["id"],
        "name": repo["name"],
        "created_at": repo["created_at"],
        "first_seen": first_seen,
        "source": source,
        "stars_at_first_seen": repo["stars"],
        "language": repo["language"],
        "license": repo["license"],
        "fork": repo["fork"],
        "description": repo["description"],
    }


def discovery_days(now: datetime, days: int = DISCOVERY_DAYS) -> list[str]:
    today = now.astimezone(timezone.utc).date()
    return [(today - timedelta(days=offset)).isoformat() for offset in range(days)]


def parse_trending(page: str) -> list[dict[str, Any]]:
    """Read repo names and "stars today" from the Trending page HTML."""
    rows = []
    for article in _ARTICLE.findall(page):
        link = _HEADING_LINK.search(article)
        if not link:
            continue
        name = html.unescape(link.group(1)).strip().strip("/")
        if not REPO_NAME.match(name):
            continue
        gained = _STARS_TODAY.search(article)
        rows.append(
            {
                "rank": len(rows) + 1,
                "name": name,
                "stars_today": int(gained.group(1).replace(",", "")) if gained else None,
            }
        )
    return rows


def search_day(gql: Gql, day: str, pause: Callable[[float], None]) -> Fetched:
    """All repos created on `day` with at least MIN_STARS stars."""
    query = f"created:{day} stars:>={MIN_STARS} sort:stars-desc"
    out = Fetched()
    cursor = None
    try:
        while True:
            data, errors = gql(SEARCH_QUERY, {"q": query, "after": cursor})
            if errors:
                out.errors.append(f"search {day}: {errors[0].get('message', 'error')}")
            out.note(data)
            result = data["search"]
            out.total = result["repositoryCount"]
            _keep_valid(result["nodes"], out, f"search {day}")
            if not result["pageInfo"]["hasNextPage"]:
                break
            cursor = result["pageInfo"]["endCursor"]
            pause(PAUSE_SECONDS)
    except Exception as error:  # noqa: BLE001 - a worker must never take the run down
        # Covers failed calls and unexpected shapes such as `"search": null`.
        # Pages fetched before the failure are kept.
        out.errors.append(f"search {day}: {_describe(error)}")
    return out


def lookup_by_name(gql: Gql, names: list[str]) -> Fetched:
    """Fetch repos by owner/name in one aliased query (used for Trending)."""
    out = Fetched()
    names = [name for name in names if REPO_NAME.match(name)]
    if not names:
        return out
    parts = []
    variables: dict[str, Any] = {}
    declared = []
    for index, name in enumerate(names):
        owner, repo = name.split("/", 1)
        variables[f"o{index}"], variables[f"n{index}"] = owner, repo
        declared.append(f"$o{index}: String!, $n{index}: String!")
        parts.append(f"r{index}: repository(owner: $o{index}, name: $n{index}) {{ ...RepoFields }}")
    query = (
        REPO_FRAGMENT
        + f"query ByName({', '.join(declared)}) {{ {' '.join(parts)} "
        + "rateLimit { cost remaining resetAt } }"
    )
    try:
        data, _errors = gql(query, variables)  # a missing repo is null plus an error: fine
        out.note(data)
        nodes = [node for key, node in data.items() if key != "rateLimit"]
    except Exception as error:  # noqa: BLE001
        out.errors.append(f"trending lookup: {_describe(error)}")
        return out
    _keep_valid(nodes, out, "trending lookup")
    return out


def refresh_batch(gql: Gql, batch: list[str]) -> Fetched:
    """Current counts for up to 100 known repos, and which of them are gone."""
    out = Fetched()
    label = f"refresh batch starting {batch[0]}"
    try:
        data, errors = gql(NODES_QUERY, {"ids": batch})
        out.note(data)
        nodes = data["nodes"]
        if len(nodes) != len(batch):
            raise ValueError(f"asked for {len(batch)} nodes, got {len(nodes)}")
    except Exception as error:  # noqa: BLE001
        out.errors.append(f"{label}: {_describe(error)}")
        return out
    # A repo is retired only when GitHub says NOT_FOUND for exactly that node.
    # Any other empty answer (a timeout, a partial response) is a problem to
    # report and retry next run, because retiring is permanent.
    confirmed_missing = {
        error["path"][1]
        for error in errors
        if error.get("type") == "NOT_FOUND"
        and isinstance(error.get("path"), list)
        and len(error["path"]) == 2
        and error["path"][0] == "nodes"
    }
    for index, (wanted, node) in enumerate(zip(batch, nodes)):
        if node and node.get("id"):
            _keep_valid([node], out, label)
        elif index in confirmed_missing:
            out.gone.append(wanted)  # deleted or made private
        else:
            out.errors.append(f"{label}: no data for {wanted} and no NOT_FOUND; kept on the watchlist")
    return out


def collect(
    data_dir: Path,
    *,
    now: datetime | None = None,
    gql: Gql | None = None,
    fetch_trending: Callable[[], str] | None = None,
    pause: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
    workers: int = WORKERS,
) -> RunReport:
    now = now or datetime.now(timezone.utc)
    stamp = store.iso(now)
    if gql is None:
        token = github.read_token()
        gql = lambda query, variables: github.graphql(query, variables, token=token)  # noqa: E731
    fetch_trending = fetch_trending or github.fetch_trending_html

    report = RunReport(started_at=stamp)
    registry = store.load_registry(data_dir)
    gone_before = store.load_gone(data_dir)
    seen: dict[str, dict[str, Any]] = {}
    source: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        # 1. Discover
        days = discovery_days(now)
        for day, fetched in zip(days, pool.map(lambda d: search_day(gql, d, pause), days)):
            _merge(report, fetched)
            if fetched.total > SEARCH_RESULT_CAP:
                report.truncated_days.append(day)
            for repo in fetched.repos:
                seen.setdefault(repo["id"], repo)
                source.setdefault(repo["id"], "search-new")
        report.discovered = len(seen)
        log(f"discover: {report.discovered} repos from {len(days)} day slices")

        # 2. Benchmark
        trending: list[dict[str, Any]] = []
        try:
            trending = parse_trending(fetch_trending())
            if not trending:
                report.errors.append("trending: page parsed to zero repos (layout changed?)")
        except github.GitHubError as error:
            report.errors.append(f"trending: {error}")
        if trending:
            known_names = {repo["name"].lower() for repo in seen.values()}
            missing = [row["name"] for row in trending if row["name"].lower() not in known_names]
            fetched = lookup_by_name(gql, missing)
            _merge(report, fetched)
            for repo in fetched.repos:
                seen.setdefault(repo["id"], repo)
                source.setdefault(repo["id"], "trending")
            ids_by_name = {repo["name"].lower(): repo["id"] for repo in seen.values()}
            store.append_jsonl(
                store.trending_path(data_dir, now),
                (
                    {"ts": stamp, **row, "id": ids_by_name.get(row["name"].lower())}
                    for row in trending
                ),
            )
        report.trending_rows = len(trending)
        log(f"benchmark: {report.trending_rows} repos on Trending")

        # 3. Refresh
        stale = [rid for rid in registry if rid not in seen and rid not in gone_before]
        batches = [stale[start : start + PAGE_SIZE] for start in range(0, len(stale), PAGE_SIZE)]
        gone_now: list[str] = []
        for fetched in pool.map(lambda batch: refresh_batch(gql, batch), batches):
            _merge(report, fetched)
            gone_now.extend(fetched.gone)
            report.refreshed += len(fetched.repos)
            for repo in fetched.repos:
                seen.setdefault(repo["id"], repo)
        report.gone = len(gone_now)
        log(f"refresh: {report.refreshed} repos updated, {report.gone} gone")

    # 4. Store
    if seen:
        path = store.write_snapshot(
            data_dir, now, (snapshot_row(seen[rid]) for rid in sorted(seen))
        )
        report.snapshot_file = path.relative_to(data_dir).as_posix()
        report.snapshot_rows = len(seen)
    else:
        report.errors.append("snapshot: nothing collected")
    new_ids = sorted(rid for rid in seen if rid not in registry)
    report.new_repos = store.append_jsonl(
        data_dir / store.REGISTRY,
        (registry_row(seen[rid], stamp, source.get(rid, "refresh")) for rid in new_ids),
    )
    store.append_jsonl(data_dir / store.GONE, ({"id": rid, "ts": stamp} for rid in gone_now))

    report.finished_at = store.iso(datetime.now(timezone.utc))
    store.append_jsonl(data_dir / store.RUNS, [report.__dict__ | {"ok": report.ok}])
    log(
        f"store: {report.snapshot_rows} rows in {report.snapshot_file or '(none)'}, "
        f"{report.new_repos} new repos, {report.api_calls} API calls, "
        f"rate cost {report.rate_cost}, remaining {report.rate_remaining}"
    )
    for problem in report.errors:
        log(f"ERROR {problem}")
    for day in report.truncated_days:
        log(f"WARNING day {day} has more than {SEARCH_RESULT_CAP} results; the tail is missed")
    return report
