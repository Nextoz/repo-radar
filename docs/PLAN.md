# Repo Radar - Build Plan

The working plan. Each finished version is logged in [ITERATIONS.md](ITERATIONS.md) and each choice in [DECISIONS.md](DECISIONS.md).

## What the product is

**An early-warning system for open source, with an X-ray for the code.**

1. **Radar:** shows interesting repos when they *start* to become popular, days before they reach GitHub Trending. One general lane and one personal lane.
2. **X-ray:** explains how a repo works: its external dependencies, how its files connect, which functions and classes pass between them, and what each part is for.

**The problem it solves:** "I find them on the Trending page, and that is too late."

### How I know it works

| Measure | Target | How it is measured |
|---|---|---|
| **Lead time** | Flagged at least 2 days before the repo appears on GitHub Trending | The pipeline records both timestamps from day one |
| **Hit rate** | Most flagged repos later reach Trending or keep growing | Same records, 14 days later |
| **Ranking agreement** | The "For you" order agrees with my own rating | About 30 repos rated by hand |
| **X-ray accuracy** | Every drawn connection exists in the code | The validator's rejected-claim count per run |

## Spike findings (13 Nov evening, real calls)

| Probe | Result | Consequence |
|---|---|---|
| GH Archive hourly file | Only 4,087 events and 261 stars in one hour | **Not usable.** Star events there fell from about 6 million a month (2024) to about 84,000 so far this month |
| OSS Insight trends API | Returns empty with a notice: event capture fell to about 0.3% of baseline, unavailable since 1 Mar 2026 | Confirms it. No third party has the star firehose any more |
| GraphQL `stargazers` with `starredAt` | Empty list (REST gave 404 this morning) | **No star history anywhere.** Growth can only come from my own snapshots |
| GraphQL search, 100 repos with stars, forks, dates, language, licence, topics | Works, costs 1 rate-limit point of 5,000 an hour | Wide, frequent snapshots are cheap |
| Pool sizes | 2,553 repos created in the last 7 days with 10+ stars; 5,923 created in 30 days with 50+ stars; 35,373 older repos with 50-2,000 stars pushed in the last 2 days | A watchlist of 5,000-10,000 repos is realistic. Search returns at most 1,000 per query, so queries must be sliced by date and star range |
| `github.com/trending` | Parses: repo names and "stars today" | Use it as the **benchmark to beat**, recorded every run. Not as the main source |
| Hacker News API | Works: recent stories linking to github.com, with points and time | Early signal source |
| Lobsters `newest.json` | Works; no GitHub links in the newest 25 at the time | Minor source, add later |
| A user's starred list with timestamps | Works (tested on a public account) | "Scouts" signal works: a hand-picked list of developers whose stars are an early signal |
| A top "new" repo | 7,244 stars and 2,591 forks in 4 days | Star inflation is real; a fork-to-star ratio that high must be flagged |
| Hugo on GitHub Pages | Proven pattern: build in Actions, publish with `actions/deploy-pages` | Reuse it |

**Not verified yet:** the rate limit of the built-in token inside GitHub Actions, how late scheduled Actions really run, and all AI cost figures.

**Consequence for the schedule:** lead time cannot be backtested, because the history does not exist. It can only be measured from the day the collector starts. **The collector is therefore the first thing to build**, before any dashboard.

## Hosting

A static site has no server, so nothing on the page can call Claude live. Every AI result is produced in the pipeline and published as data. This is a strength: the site cannot break during a live demo.

## Architecture

```
            ┌──────────── GitHub Actions (scheduled) ────────────┐
Sources ──► │ 1 Discover   new repos, HN links, scouts' stars     │
            │ 2 Snapshot   stars/forks for the whole watchlist    │──► data branch
            │ 3 Benchmark  record github.com/trending             │    (one file per run)
            │ 4 Detect     acceleration + junk filter + quality   │
            │ 5 Judge      Claude: summary, substance, fit        │
            │ 6 X-ray      parser + Claude agent + validator      │
            │ 7 Build      Hugo renders pages from the data       │──► GitHub Pages
            │ 8 Notify     daily digest issue (emails me)         │
            └─────────────────────────────────────────────────────┘
Local CLI:  radar xray owner/repo   (same code, for live demos)
```

Steps 1-4 and 7-8 are ordinary code. Steps 5 and 6 use Claude. Each step reads files and writes files, so each can be run and tested alone.

### 1. Discover (the wide net)

| Source | What it finds | Cadence |
|---|---|---|
| Search: created in the last 30 days, 10+ stars, sliced by day | New projects | Every 3 hours |
| Search: my topics and languages (Bicep, Azure, agents, MCP, security, DevOps) with a lower star bar | Niche repos for the personal lane | Daily |
| Hacker News: stories linking to github.com | Projects being discussed now, of any age | Hourly |
| Scouts: recent stars of a hand-picked list of developers | Early and already filtered by taste | Daily |
| Search: older repos, 50-2,000 stars, pushed recently | Old projects waking up | Daily, added in M2 |
| Trending page | Only used to mark "reached Trending at" | Every run |

### 2. Snapshot

Every run stores stars, forks, open issues and last push for each watchlist repo. Repos that stay flat for 14 days drop to a daily check; repos with no growth for 45 days leave the watchlist.

### 3. Detect: the breakout score

- `gain_24h` and `gain_72h` from snapshots.
- `baseline` = average daily gain over the 7 days before that.
- **Acceleration** = `gain_24h ÷ (baseline + k)`, with a minimum gain so that 2 → 6 stars does not count.
- A repo is a **breakout** when acceleration passes a threshold on two runs in a row.
- Stages shown on the card: **Spark** (under 100 stars), **Rising** (100-1,000), **Mainstream** (on Trending).

The constants are tuned on real data after the first week, not guessed now.

### 4. Junk filter and quality (code)

- **Remove:** forks, archived repos, awesome-lists, course and interview repos, empty repos.
- **Flag as inflated:** fork-to-star ratio far above normal, stars arriving in a single step, no code behind a large star count.
- **Quality signals:** several contributors, recent commits, releases, tests and CI present, a licence, a real README, issues that get answers.

### 5. Judge (Claude, structured output)

Only breakout candidates are sent, so the volume is small (expected 50-150 a day).

- Input: metadata, README excerpt and my profile, all marked as untrusted data.
- Output per repo: one-line summary, category, **substance** (real tool, thin wrapper or hype), what is new about it, **fit** 0-100 with a one-line reason.
- Model: `claude-haiku-5-5` first; compare with `claude-opus-5-5` on the hand-rated set and keep the cheapest that agrees with me.

### 6. X-ray

For each chosen repo:

1. **Fetch:** file tree, README, manifest files, source files.
2. **Parse (code):** external dependencies from manifests; the import graph from the code; for each edge, the functions and classes imported and where they are used. Python first (`ast`), then TypeScript/JavaScript.
3. **Agent (Claude, read-only tools):** groups files into modules, names them, draws the architecture map of 5-8 boxes, and explains each connection: why A needs B and what passes between them.
4. **Validate (code):** any file, edge or symbol the model names that is not in the parser output is rejected and counted.
5. **Publish:** one JSON file per repo; Hugo renders the X-ray page from it.

Views on the X-ray page: architecture map, interactive file graph with labelled edges, a file panel (what it does, what it uses, who uses it), external dependencies with their purpose, technical overview, trust panel.

### 7. The site (Hugo)

| Page | Content |
|---|---|
| **Radar** (home) | Lanes: Breaking out, For you, Just discussed (HN), Scouts' picks. Cards with stage, growth sparkline, Quality and Fit scores, the AI's reason |
| **Repo page** | Growth chart from first sighting, signals, quality breakdown, why it was flagged, link to its X-ray |
| **X-ray page** | The views listed above |
| **Scoreboard** | Lead time and hit rate, with every flagged repo and when it reached Trending |
| **How it works** | The pipeline, the models, the costs and the security design. Doubles as documentation |

"Seen since last visit" is kept in the browser. Interactive graphs run in the browser from the published JSON.

### 8. Notify

A daily GitHub issue in the repo lists the top breakouts. GitHub emails it to me, so no mail service or extra secret is needed. An RSS feed comes free from Hugo.

## Security

- The pipeline reads text written by strangers. Four layers apply: read-only tools, repo text passed as marked data, an injection scan, and the validator.
- A poisoned test repo of my own shows the attack with and without the defence.
- **Secrets:** the Anthropic API key is a GitHub Actions secret that I add myself. It never appears in code, logs, prompts or the site.
- **Public repo:** the profile file holds interests only. No personal data.
- **Spending guard:** AI steps have a hard daily cap in code, and the on-demand X-ray workflow can only be started by me.
- Workflows get the minimum permissions they need, and third-party actions are pinned to a commit.

## Repository layout

```
repo-radar/
  radar/              Python package: discover, snapshot, detect, judge, xray, validate
  radar/cli.py        radar discover | snapshot | detect | judge | xray | build-data
  tests/fixtures/     real captured API responses and real parser output
  site/               Hugo site (layouts, assets, content adapters)
  profile/            interests.md, scouts.txt
  .github/workflows/  collect.yml, judge.yml, xray.yml, site.yml, pr-checks.yml
  docs/               PLAN.md, ITERATIONS.md, DECISIONS.md
  AGENTS.md           how an agent should work in this repo
(data branch)         snapshots/, events/, scores/, xray/
```

## Milestones

Each one ends with something that works and is published.

| By | Milestone | Done when |
|---|---|---|
| **Sun 15 Nov** | **M0 Collector** | Repo exists; discovery and snapshots run on a schedule; Trending is recorded; three runs in a row finished with exit code 0 and new data files |
| Fri 20 Nov | M1 Radar live | Hugo site on Pages; Breaking out lane ranked by acceleration; junk filter and quality signals; repo pages with growth chart |
| Thu 26 Nov | M2 AI ranking | Summaries, substance and fit; For you lane; Hacker News and scouts as sources; daily digest issue; model comparison measured |
| Thu 3 Dec | M3 X-ray core | Python repos: dependencies, labelled file graph, architecture map, per-connection explanations, validator; X-ray built for the daily top breakouts |
| Tue 8 Dec | M4 Trust and proof | Trust panel; injection defence with the poisoned repo; Scoreboard page with real lead times |
| Fri 11 Dec | M5 Freeze | Three well-known repos X-rayed and cached; local CLI demo works with the network off |

**Whole-system review** after M2 and again at M5.

## Features

**Core (must work by 11 Dec)**

- Wide discovery and frequent snapshots
- Breakout detection by acceleration, with stages
- Junk filter and star-inflation flag
- Quality score and Fit score with reasons
- General and personal lanes
- Hacker News and scouts signals
- Daily digest
- X-ray for Python: dependencies, labelled connections, architecture map, explanations
- Validator and rejected-claim count
- Trust panel and injection defence
- Scoreboard with lead time
- "How it works" page

**Next (if time allows)**

- TypeScript/JavaScript X-ray
- Explanation levels: beginner, developer, architect
- 👍/👎 on cards that feeds the ranking (through a prefilled issue handled by a workflow)
- Embeddings: "similar repos" and a pre-filter for fit
- Function-level view inside a clicked file
- Search and filters on the Radar (language, category, stage)

**Later (portfolio growth)**

- "Follow a request" animation
- Compare two repos side by side
- Weekly written report
- Topic pages (for example "what is moving in Bicep this month")
- Release watching for repos I marked as interesting
- More sources: Lobsters, Reddit, package registries
- More languages in the X-ray (Go, Rust, C#)

## Testing

- **Fixtures come from real captures.** The spike responses from 13 Nov are saved into `tests/fixtures/` first; no invented API shapes.
- **Detection:** replay stored snapshots and check that known breakouts are flagged and flat repos are not.
- **Parser:** run on three real repos and compare the graph with the actual imports.
- **Judge:** agreement with my hand ratings.
- **X-ray:** I judge the architecture map for three repos I know well.
- **Injection:** the poisoned repo is flagged and the output does not follow it.
- **Pipeline health:** every scheduled run is judged by its exit code and the age of its newest data file; the site shows "data updated at".

## Cost and limits (estimates, not measured)

| Item | Estimate |
|---|---|
| GitHub Actions, Pages | Free for a public repo |
| GitHub API | Well inside the limits found in the spike |
| Judge, about 100 repos a day on Haiku 5.5 | A few cents a day |
| X-ray on Opus 5.5 | About $0.40 a repo; two a day is about $25 a month |

The X-ray is the only real cost. The daily number is a setting.

## Risks

| Risk | Answer |
|---|---|
| Too little data to prove lead time | The collector started on 13 Nov; every week adds evidence |
| Scope: this is a large product | Milestones are ordered so the product works after each one; the "Next" list is cut first |
| The breakout threshold produces noise | Tune it on the first week of real data; require two runs in a row |
| Scheduled Actions run late or get paused | Health check on data age; the pipeline also runs from my PC with the same CLI |
| The data branch grows large | One compressed file per run; old snapshots are thinned to daily |
| Star-farmed repos fill the top lane | Inflation flag and the AI substance check |
| GitHub changes or blocks the Trending page | It is only the benchmark; the Radar does not depend on it |

## Open decisions

1. **Site address:** the default Pages address or a custom subdomain.
2. **X-ray budget:** how many automatic X-rays a day (suggested: two).
3. **Scouts list:** 10-20 developers whose stars are a trusted early signal.

## How the work continues between sessions

- This file is the plan.
- `docs/ITERATIONS.md` logs each version: what was tried, what failed, what changed.
- `docs/DECISIONS.md` records each choice with its reason.
- One GitHub issue per milestone, with the "done when" line as its checklist.
- A new session starts by reading `docs/PLAN.md` and the open milestone issue.
