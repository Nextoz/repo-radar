"""Capture real GitHub responses into tests/fixtures.

Fixtures must come from the real API, never be written by hand, so the tests
exercise the shapes GitHub actually sends. Run:  python scripts/capture_fixtures.py
"""

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from radar import collect, github  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def save(name: str, payload) -> None:
    (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("saved", name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    day = (datetime.now(timezone.utc).date() - timedelta(days=3)).isoformat()
    query = f"created:{day} stars:>={collect.MIN_STARS} sort:stars-desc"

    data, errors = github.graphql(collect.SEARCH_QUERY, {"q": query, "after": None})
    data["search"]["nodes"] = data["search"]["nodes"][:6]  # keep the fixture small
    save("search_page.json", {"variables": {"q": query}, "data": data, "errors": errors})

    # A query that matches nothing, to capture the real shape of an empty page.
    empty_query = f"created:2007-01-01 stars:>={collect.MIN_STARS} sort:stars-desc"
    empty, empty_errors = github.graphql(collect.SEARCH_QUERY, {"q": empty_query, "after": None})
    save("search_empty.json", {"variables": {"q": empty_query}, "data": empty, "errors": empty_errors})

    ids = [node["id"] for node in data["search"]["nodes"][:3]]
    # A well-formed id that does not exist, to capture how GitHub reports a vanished repo.
    missing = ids[0][:-4] + ("AAAA" if not ids[0].endswith("AAAA") else "BBBB")
    data2, errors2 = github.graphql(collect.NODES_QUERY, {"ids": ids + [missing]})
    save("nodes_with_missing.json", {"variables": {"ids": ids + [missing]}, "data": data2, "errors": errors2})

    page = github.fetch_trending_html()
    articles = re.findall(r'<article class="Box-row">.*?</article>', page, re.S)
    (OUT / "trending_articles.html").write_text("\n".join(articles) + "\n", encoding="utf-8")
    print("saved trending_articles.html:", len(articles), "articles from", len(page), "bytes")

    names = [row["name"] for row in collect.parse_trending(page)][:3] + ["github/this-repo-does-not-exist-radar"]
    captured = {}

    def recording(query, variables):
        result = github.graphql(query, variables)
        captured.update(variables=variables, data=result[0], errors=result[1])
        return result

    collect.lookup_by_name(recording, names)
    save("by_name_with_missing.json", captured)


if __name__ == "__main__":
    main()
