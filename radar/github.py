"""Minimal GitHub client: GraphQL calls and the public Trending page.

Standard library only, so the collector runs anywhere Python does.
The token is read from the environment and never logged.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

GRAPHQL_URL = "https://api.github.com/graphql"
TRENDING_URL = "https://github.com/trending"
USER_AGENT = "repo-radar-collector"
RETRY_STATUS = {403, 429, 500, 502, 503, 504}


class GitHubError(RuntimeError):
    """A GitHub call failed after all retries."""


def read_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise GitHubError("Set GITHUB_TOKEN or GH_TOKEN to a GitHub token.")
    return token


def _wait_seconds(attempt: int, retry_after: str | None) -> float:
    if retry_after and retry_after.isdigit():
        return min(float(retry_after), 120.0)
    return min(5.0 * 2**attempt, 120.0)


def graphql(
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    token: str | None = None,
    retries: int = 4,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run one GraphQL query. Returns (data, errors).

    GitHub can answer with data *and* errors, for example when one requested
    node no longer exists. Those errors are returned to the caller. A response
    with no data at all is retried and then raised.
    """
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token or read_token()}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    last_problem = "no attempt made"
    for attempt in range(retries + 1):
        request = urllib.request.Request(GRAPHQL_URL, data=body, headers=headers)
        retry_after = None
        try:
            with opener(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last_problem = f"HTTP {error.code}"
            if error.code not in RETRY_STATUS:
                raise GitHubError(last_problem) from error
            retry_after = error.headers.get("Retry-After") if error.headers else None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_problem = f"{type(error).__name__}: {error}"
        else:
            data = payload.get("data")
            errors = payload.get("errors") or []
            if data is not None:
                return data, errors
            last_problem = "; ".join(
                str(e.get("type") or e.get("message", "unknown error")) for e in errors
            ) or str(payload.get("message", "empty response"))
        if attempt < retries:
            sleep(_wait_seconds(attempt, retry_after))
    raise GitHubError(f"GraphQL call failed after {retries + 1} attempts: {last_problem}")


def fetch_trending_html(
    *,
    retries: int = 2,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Download the public Trending page (no token: it is a public web page)."""
    last_problem = "no attempt made"
    for attempt in range(retries + 1):
        request = urllib.request.Request(
            TRENDING_URL, headers={"User-Agent": f"Mozilla/5.0 ({USER_AGENT})"}
        )
        try:
            with opener(request, timeout=60) as response:
                return response.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as error:
            last_problem = f"{type(error).__name__}: {error}"
        if attempt < retries:
            sleep(_wait_seconds(attempt, None))
    raise GitHubError(f"Trending page failed after {retries + 1} attempts: {last_problem}")
