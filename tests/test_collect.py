"""Collector tests. Every GitHub payload here was captured from the real API
by scripts/capture_fixtures.py; none of it is written by hand."""

import copy
import io
import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

from radar import cli, collect, github, store

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


SEARCH = load("search_page.json")
EMPTY = load("search_empty.json")
NODES = load("nodes_with_missing.json")
BY_NAME = load("by_name_with_missing.json")
TRENDING_HTML = (FIXTURES / "trending_articles.html").read_text(encoding="utf-8")

SEARCH_DAY = SEARCH["variables"]["q"].split()[0].removeprefix("created:")
SEARCH_NODES = SEARCH["data"]["search"]["nodes"]
STILL_THERE = {node["id"]: node for node in NODES["data"]["nodes"] if node}


class FakeGitHub:
    """Replays captured responses and records what was asked."""

    def __init__(self, fail_search: bool = False):
        self.fail_search = fail_search
        self.requested_ids: list[str] = []
        self.searched_days: list[str] = []

    def __call__(self, query, variables):
        if "query Search" in query:
            if self.fail_search:
                raise github.GitHubError("GraphQL call failed after 5 attempts: HTTP 502")
            day = variables["q"].split()[0].removeprefix("created:")
            self.searched_days.append(day)
            first_page = day == SEARCH_DAY and variables["after"] is None
            return copy.deepcopy((SEARCH if first_page else EMPTY)["data"]), []
        if "query Nodes" in query:
            self.requested_ids.extend(variables["ids"])
            nodes = [copy.deepcopy(STILL_THERE.get(rid)) for rid in variables["ids"]]
            return {"nodes": nodes, "rateLimit": NODES["data"]["rateLimit"]}, NODES["errors"]
        if "query ByName" in query:
            return copy.deepcopy(BY_NAME["data"]), BY_NAME["errors"]
        raise AssertionError("unexpected query")


def run(data_dir: Path, now: datetime, fake: FakeGitHub) -> collect.RunReport:
    return collect.collect(
        data_dir,
        now=now,
        gql=fake,
        fetch_trending=lambda: TRENDING_HTML,
        pause=lambda _seconds: None,
        log=lambda _line: None,
    )


class ParsingTests(unittest.TestCase):
    def test_normalize_flattens_a_real_search_node(self):
        node = SEARCH_NODES[0]
        repo = collect.normalize(node)
        self.assertEqual(repo["id"], node["id"])
        self.assertEqual(repo["name"], node["nameWithOwner"])
        self.assertEqual(repo["stars"], node["stargazerCount"])
        self.assertEqual(repo["forks"], node["forkCount"])
        self.assertGreaterEqual(repo["stars"], collect.MIN_STARS)

    def test_normalize_handles_missing_language_and_licence(self):
        for node in SEARCH_NODES:
            repo = collect.normalize(node)
            expected = node["primaryLanguage"]["name"] if node["primaryLanguage"] else None
            self.assertEqual(repo["language"], expected)
            expected = node["licenseInfo"]["spdxId"] if node["licenseInfo"] else None
            self.assertEqual(repo["license"], expected)

    def test_parse_trending_reads_every_article_on_the_real_page(self):
        rows = collect.parse_trending(TRENDING_HTML)
        self.assertEqual(len(rows), TRENDING_HTML.count('<article class="Box-row">'))
        self.assertGreater(len(rows), 5)
        self.assertEqual([row["rank"] for row in rows], list(range(1, len(rows) + 1)))
        for row in rows:
            self.assertRegex(row["name"], collect.REPO_NAME)
            self.assertIsInstance(row["stars_today"], int)
            self.assertGreater(row["stars_today"], 0)

    def test_parse_trending_returns_nothing_for_a_changed_layout(self):
        self.assertEqual(collect.parse_trending("<html><body>Sign in</body></html>"), [])

    def test_discovery_days_cover_the_window_ending_today(self):
        now = datetime(2026, 11, 13, 23, 30, tzinfo=timezone.utc)
        days = collect.discovery_days(now)
        self.assertEqual(len(days), collect.DISCOVERY_DAYS)
        self.assertEqual(days[0], "2026-11-13")
        self.assertEqual(days[-1], "2026-10-15")


class LookupTests(unittest.TestCase):
    def test_refresh_separates_live_repos_from_vanished_ones(self):
        ids = NODES["variables"]["ids"]
        fetched = collect.refresh_batch(FakeGitHub(), ids)
        self.assertEqual([repo["id"] for repo in fetched.repos], ids[:3])
        self.assertEqual(fetched.gone, ids[3:])
        self.assertEqual(fetched.errors, [])
        self.assertEqual(fetched.calls, 1)

    def test_lookup_by_name_skips_a_repo_that_does_not_exist(self):
        names = ["a/one", "b/two", "c/three", "d/missing"]
        fetched = collect.lookup_by_name(FakeGitHub(), names)
        self.assertEqual(len(fetched.repos), 3)
        self.assertEqual(fetched.errors, [])

    def test_lookup_by_name_never_puts_names_into_the_query_text(self):
        seen = {}

        def spy(query, variables):
            seen.update(query=query, variables=variables)
            return copy.deepcopy(BY_NAME["data"]), []

        collect.lookup_by_name(spy, ["owner/repo", 'evil"} injected/x y'])
        self.assertNotIn("owner", seen["query"].replace("owner:", ""))
        self.assertEqual(seen["variables"], {"o0": "owner", "n0": "repo"})


class CollectRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Path(self.tmp.name)
        self.now = datetime.fromisoformat(SEARCH_DAY).replace(tzinfo=timezone.utc) + timedelta(
            days=3, hours=9
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_first_run_stores_snapshot_registry_trending_and_run_summary(self):
        report = run(self.data, self.now, FakeGitHub())
        self.assertTrue(report.ok, report.errors)
        expected = len(SEARCH_NODES) + 3  # search results + three repos found via Trending
        self.assertEqual(report.snapshot_rows, expected)
        self.assertEqual(report.new_repos, expected)

        snapshot = list(store.read_jsonl(self.data / report.snapshot_file))
        self.assertEqual(len(snapshot), expected)
        self.assertEqual(set(snapshot[0]), {"id", "stars", "forks", "pushed_at"})
        by_id = {row["id"]: row for row in snapshot}
        self.assertEqual(by_id[SEARCH_NODES[0]["id"]]["stars"], SEARCH_NODES[0]["stargazerCount"])

        registry = store.load_registry(self.data)
        self.assertEqual(registry[SEARCH_NODES[0]["id"]]["source"], "search-new")
        self.assertEqual(sum(1 for r in registry.values() if r["source"] == "trending"), 3)

        trending = list(store.read_jsonl(store.trending_path(self.data, self.now)))
        self.assertEqual(len(trending), TRENDING_HTML.count('<article class="Box-row">'))
        self.assertEqual(trending[0]["ts"], store.iso(self.now))

        runs = list(store.read_jsonl(self.data / store.RUNS))
        self.assertEqual(len(runs), 1)
        self.assertTrue(runs[0]["ok"])
        self.assertEqual(runs[0]["api_calls"], report.api_calls)
        self.assertEqual(report.api_calls, collect.DISCOVERY_DAYS + 2)  # 30 days, 1 extra page, 1 lookup

    def test_every_day_in_the_window_is_searched(self):
        fake = FakeGitHub()
        run(self.data, self.now, fake)
        self.assertEqual(len(set(fake.searched_days)), collect.DISCOVERY_DAYS)
        self.assertIn(SEARCH_DAY, fake.searched_days)

    def test_second_run_adds_a_snapshot_but_no_duplicate_registry_lines(self):
        first = run(self.data, self.now, FakeGitHub())
        second = run(self.data, self.now + timedelta(hours=3), FakeGitHub())
        self.assertEqual(second.new_repos, 0)
        lines = (self.data / store.REGISTRY).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), first.new_repos)
        self.assertEqual(len(store.list_snapshots(self.data)), 2)

    def test_repos_outside_the_window_are_refreshed_and_vanished_ones_retired(self):
        run(self.data, self.now, FakeGitHub())
        later = self.now + timedelta(days=45)  # the search day has left the 30-day window

        fake = FakeGitHub()
        report = run(self.data, later, fake)
        search_ids = [node["id"] for node in SEARCH_NODES]
        self.assertTrue(set(search_ids) <= set(fake.requested_ids))
        self.assertEqual(report.refreshed, len(STILL_THERE))
        self.assertEqual(report.gone, len(search_ids) - len(STILL_THERE))
        self.assertEqual(store.load_gone(self.data), set(search_ids) - set(STILL_THERE))

        again = FakeGitHub()
        run(self.data, later + timedelta(hours=3), again)
        self.assertFalse(store.load_gone(self.data) & set(again.requested_ids))

    def test_a_failing_search_is_recorded_and_the_run_reports_failure(self):
        report = run(self.data, self.now, FakeGitHub(fail_search=True))
        self.assertFalse(report.ok)
        self.assertEqual(sum("search" in e for e in report.errors), collect.DISCOVERY_DAYS)
        self.assertEqual(report.snapshot_rows, 3)  # Trending repos were still stored
        runs = list(store.read_jsonl(self.data / store.RUNS))
        self.assertFalse(runs[0]["ok"])

    def test_an_unreadable_trending_page_fails_the_run_but_keeps_the_snapshot(self):
        report = collect.collect(
            self.data,
            now=self.now,
            gql=FakeGitHub(),
            fetch_trending=lambda: "<html>layout changed</html>",
            pause=lambda _s: None,
            log=lambda _l: None,
        )
        self.assertFalse(report.ok)
        self.assertEqual(report.snapshot_rows, len(SEARCH_NODES))

    def test_status_is_healthy_after_a_fresh_run_and_stale_without_data(self):
        self.assertEqual(cli.main(["status", "--data", str(self.data)]), 1)
        run(self.data, datetime.now(timezone.utc), FakeGitHub())
        self.assertEqual(cli.main(["status", "--data", str(self.data)]), 0)
        self.assertEqual(
            cli.main(["status", "--data", str(self.data), "--max-age-hours", "-1"]), 1
        )


class StoreTests(unittest.TestCase):
    def test_snapshot_path_round_trips_its_timestamp(self):
        moment = datetime(2026, 11, 13, 18, 5, 9, tzinfo=timezone.utc)
        path = store.snapshot_path(Path("data"), moment)
        self.assertEqual(path.as_posix(), "data/snapshots/2026/11/13/180509Z.jsonl.gz")
        self.assertEqual(store.snapshot_time(path), moment)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class GraphqlClientTests(unittest.TestCase):
    def test_retries_a_502_and_then_returns_data(self):
        calls, waits = [], []

        def opener(request, timeout):
            calls.append(request)
            if len(calls) < 3:
                raise urllib.error.HTTPError(request.full_url, 502, "Bad Gateway", {}, None)
            return _Response(json.dumps({"data": SEARCH["data"]}).encode("utf-8"))

        data, errors = github.graphql("q", token="t", opener=opener, sleep=waits.append)
        self.assertEqual(data["search"]["repositoryCount"], SEARCH["data"]["search"]["repositoryCount"])
        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 3)
        self.assertEqual(waits, [5.0, 10.0])

    def test_returns_partial_data_together_with_its_errors(self):
        payload = {"data": NODES["data"], "errors": NODES["errors"]}
        opener = lambda request, timeout: _Response(json.dumps(payload).encode("utf-8"))  # noqa: E731
        data, errors = github.graphql("q", token="t", opener=opener, sleep=lambda _s: None)
        self.assertIsNone(data["nodes"][-1])
        self.assertEqual(errors[0]["type"], "NOT_FOUND")

    def test_gives_up_when_there_is_never_any_data(self):
        payload = {"errors": [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]}
        calls = []

        def opener(request, timeout):
            calls.append(1)
            return _Response(json.dumps(payload).encode("utf-8"))

        with self.assertRaisesRegex(github.GitHubError, "RATE_LIMITED"):
            github.graphql("q", token="t", retries=2, opener=opener, sleep=lambda _s: None)
        self.assertEqual(len(calls), 3)

    def test_a_401_is_not_retried(self):
        calls = []

        def opener(request, timeout):
            calls.append(1)
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)

        with self.assertRaisesRegex(github.GitHubError, "HTTP 401"):
            github.graphql("q", token="t", opener=opener, sleep=lambda _s: None)
        self.assertEqual(len(calls), 1)

    def test_the_token_never_appears_in_an_error_message(self):
        def opener(request, timeout):
            raise urllib.error.URLError("connection reset")

        with self.assertRaises(github.GitHubError) as caught:
            github.graphql("q", token="secret-token", retries=0, opener=opener, sleep=lambda _s: None)
        self.assertNotIn("secret-token", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
