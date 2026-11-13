# Repo Radar

**An early-warning radar for open source.** It spots repositories when they
*start* to take off, days before they reach GitHub Trending, and (soon)
explains how their code fits together.

> Status: milestone 0. The collector runs every three hours and stores star
> counts. The dashboard, the AI ranking and the code X-ray come next; see
> [the plan](docs/PLAN.md).

## Why

GitHub Trending shows a project when everyone has already found it. To see a
project earlier you need its star *growth*, and GitHub publishes no star
history: not in the REST API, not in GraphQL, and the public event archives
now carry a fraction of a percent of star events.

So Repo Radar counts for itself. It watches thousands of young repositories,
records their stars every few hours, and ranks by acceleration instead of
size.

## How it works today

```
GitHub Actions, every 3 hours
  1 Discover   repos created in the last 30 days with 10+ stars
  2 Benchmark  record what github.com/trending shows right now
  3 Refresh    current counts for every other watched repo
  4 Store      one snapshot file on the data branch
```

The Trending page is recorded on purpose: it is the baseline to beat. For
every repo the radar flags, the data will show how many days later (if ever)
it reached Trending.

## Run it

Python 3.12 or newer, no dependencies.

```bash
git clone https://github.com/Nextoz/repo-radar && cd repo-radar
git worktree add data data            # the data branch, checked out beside the code
GH_TOKEN="$(gh auth token)" python -m radar collect --data data
python -m radar status --data data    # is the newest snapshot fresh?
python -m unittest discover -s tests -t .
```

## Data

Everything lives as plain files on the [`data` branch](../../tree/data):

| File | Content |
|---|---|
| `snapshots/YYYY/MM/DD/HHMMSSZ.jsonl.gz` | Stars, forks and last push for every watched repo, one file per run |
| `repos.jsonl` | Append-only registry: when and how each repo was first seen |
| `trending/YYYY-MM.jsonl` | What GitHub Trending showed at each run |
| `gone.jsonl` | Repos that were deleted or made private |
| `runs.jsonl` | One summary line per run, including errors |

## Design rules

- **Facts from code, meaning from AI.** Counting, parsing and validating are
  ordinary code. Models are used only where judgement is needed.
- **Test with real data.** Every fixture in `tests/fixtures/` is a captured
  API response (`scripts/capture_fixtures.py`), never a hand-written one.
- **Fail loudly.** A run that could not collect everything still stores what
  it has, then exits non-zero. Health is judged by the age of the newest
  snapshot, not by the job being scheduled.
- **Untrusted input.** Repository names, descriptions and READMEs are written
  by strangers and are treated as data, never as instructions.
