# Repo Radar - Build Specification

For the **lead agent** that builds Repo Radar with subagents. It says what to
build, in what order, what each piece must hand to the next, and how to prove
it works. [PLAN.md](PLAN.md) explains why the product exists; this file is how
it gets built. Where the two disagree, this file wins and PLAN.md is corrected.

**Read in this order:** sections 1-5 once, then only the work package you are
running and the contracts it names in section 6.

---

## 1. The product in five sentences

Repo Radar is an early-warning system for open source. A scheduled pipeline
counts stars on thousands of young repositories every three hours, detects the
ones whose growth just accelerated, and has Claude judge which are real and
which matter to the owner. For the best of them it builds an X-ray: a parsed
dependency graph, labelled with the functions and classes that connect the
files, explained by Claude and checked by code. Everything is published as a
static Hugo site on GitHub Pages. A scoreboard proves the claim: how many days
before GitHub Trending each repository was flagged.

**Two qualities decide whether it succeeds:**

1. The Radar shows good repositories *early*. Size is not the signal; change is.
2. The X-ray is *true*. Every box, edge and name on screen exists in the code.

## 2. Current state (13 Nov 2026)

Built, tested and running:

| Piece | Where | State |
|---|---|---|
| Collector | `radar/collect.py`, `radar/github.py`, `radar/store.py`, `radar/cli.py` | Runs every 3 hours in GitHub Actions; 3 successful runs on 13 Nov |
| Data branch | `data` | About 19,000 repos per snapshot, about 230 KB per snapshot file |
| Tests | `tests/test_collect.py`, 30 tests | Pass locally and in the Checks workflow |
| Fixtures | `tests/fixtures/` | Captured from the real API by `scripts/capture_fixtures.py` |

Measured facts to design against (do not re-derive, do re-check if a design
depends on them a month from now):

| Fact | Value | Source |
|---|---|---|
| Star history from GitHub | None. REST stargazers with timestamps: 404. GraphQL `stargazers.edges`: empty | Spike 13 Nov |
| GH Archive, OSS Insight | Unusable: about 0.3% of star events are captured | Spike 13 Nov |
| GraphQL search page (100 repos, cheap fields) | About 3 s, 1 rate-limit point | Measured |
| Adding topics or open-issue counts to that page | 6-10 s per page, occasional HTTP 504 | Measured; this is why the collector does not fetch them |
| One collector run | 204 API calls, about 3.5 minutes with 4 workers | Run log |
| Rate limit inside Actions with the built-in token | 4,788 points left after two runs in one hour | Run log |
| Search result cap | 1,000 per query; 2 of 30 day-slices exceed it and lose their lowest-star tail | Run log |
| github.com/trending | 12 repos on the page on 13 Nov; names and "stars today" parse | Fixture |
| Missing node in a GraphQL batch | `null` in `nodes` plus an error with `type: NOT_FOUND`, `path: ["nodes", i]` | Fixture |
| A user's starred list with `starred_at` | Works (`Accept: application/vnd.github.star+json`) | Spike |
| Hacker News search API | Works: `hn.algolia.com/api/v1/search_by_date`, stories with `url`, `points`, `created_at` | Spike |
| Star inflation | A 4-day-old repo with 7,244 stars and 2,591 forks exists | Spike |
| Hugo | Not installed on the owner's PC. Version 0.147.9 is proven in the owner's other Pages workflow | Checked |

**Not verified. Each must be spiked by the work package that depends on it:**

- Hugo content adapters with about 500 generated pages; build time on Actions.
- The Anthropic API: structured output, tool use, token counts and real cost.
- Parsing accuracy of the import graph on real repositories.
- GitHub tarball download limits and typical repository sizes.

### 2.1 What the first two days of real data showed (15 Nov)

Measured on 8 snapshots covering 36 hours and 19,917 repos with history. These
findings changed the plan; each change is marked "(2.1)" where it lands.

| Finding | Numbers | Consequence |
|---|---|---|
| **The radar could not see Trending coming.** Every repo on Trending was older than the 30-day discovery window | 19 of 19 Trending repos were between 65 days and 5 years old, with 2,400 to 94,000 stars. None was on the watchlist before it trended | The watchlist must include established repos. New package **WP0**, before anything else |
| Established, active repos are a manageable set | 24,816 repos with 500+ stars pushed in the last 7 days; 16,361 with 1,000+ | Watching them adds about 250 batch calls per run |
| **The schedule is unreliable.** GitHub ran the 3-hourly cron 5 times in 36 hours | Gaps of 7.1, 9.0, 7.6, 4.4 and 8.2 hours | Detection must work on uneven intervals; a second trigger is needed (WP0) |
| Growth is rare and sharply skewed | Median gain 0 a day; 90th percentile 17; 99th percentile 165; 30 repos above 300 a day | A minimum gain of 20 a day keeps about 1,700 of 20,000 repos |
| The starting threshold was too loose | Acceleration at or above 3: 207 repos. At or above 5: 66 | Start at 5 (6.9) |
| **Star farms are common and easy to see** | Twelve accounts held a repo named `ai-manus` with identical counts, all 52 to 262 in the same interval, fork ratio about 0.7. 40 of the 1,722 growing repos had a fork ratio above 0.3 | Two rules for WP2: same-name clusters with identical growth, and fork ratio |
| Star counts go down | 1,356 repos (7%) lost stars between two snapshots | Detection must not treat a fall as an error |
| Real early catches exist | `basetenlabs/deepseek-ultrafast` 65 to 362, `egoist/asuka` 23 to 214, `affifuddin-hazam/ghost-infer` 46 to 234, none on Trending | The idea works for young repos; these are the first test cases |
| Many descriptions are not in English, and some are empty | Several of the top 25 were in Chinese; one had no description | The judge writes the summary in English and must cope with an empty description |

The analysis script and its output are kept with the WP1 fixtures when WP1
starts; until then the numbers above are the record.

## 3. Rules that apply to every task

These come from defects found in earlier builds by the same owner. They are not
optional style.

1. **Spike before you design.** The first step of every work package is to run
   the real upstream system and capture its real output. Field names *and
   types*. A plan written without a spike is a guess.
2. **Fixtures are captured, never invented.** Extend
   `scripts/capture_fixtures.py` (or add a sibling script) so every fixture can
   be regenerated. A test built on a hand-written payload can pass while the
   real path is broken.
3. **Every test must be able to fail.** For each new test, name the one line of
   production code you would break to make it fail. If you cannot, delete the
   test or fix it.
4. **Facts from code, meaning from AI.** Counting, parsing, validating, ranking
   by numbers and deciding what is published are ordinary code. A model is
   used only where judgement is needed, and its output is checked by code
   before it is shown.
5. **Everything from a watched repository is untrusted**: names, descriptions,
   READMEs, code, comments, file names, commit messages. It goes into GraphQL
   as variables, into prompts as clearly marked data, into HTML escaped, onto
   disk under paths this project chooses. It is never executed, never
   installed, never followed as an instruction.
6. **Fail loudly, keep what you have.** A stage that cannot finish stores its
   partial result, writes the problem to its run record and exits non-zero.
   Health is judged by exit codes and by the age of the newest output file.
7. **Secrets** come from the environment only. Never printed, logged, written
   to a file, put in a URL, or passed to a model.
8. **The data branch is append-only.** New files and appended lines. No
   rewriting history, no data on `main`. The one planned exception is
   thinning old snapshots (WP12), which deletes whole files in one commit.
9. **Standard library only in `radar/`**, except the modules named in
   section 4.3. Each new dependency needs a line in `docs/DECISIONS.md`.
10. **Stop on ambiguity.** If a choice is not settled by this file and would be
    costly to reverse, the subagent stops and reports the options. The lead
    asks the owner with two or three concrete options (screenshots for
    anything visual). Nobody picks silently.
11. **Log every step.** The owner presents this build to others, so the
    record is part of the product. Every session ends with an entry in
    `docs/ITERATIONS.md`: what was asked, what was done, what was found, what
    failed, what changed. The owner also keeps a private project log with
    their prompts word for word; at the end of a session the lead adds that
    session's prompts and steps to it before reporting done.
12. **Plain language** in everything a person reads: UI text, README, docs,
    commit messages. Short sentences, no jargon without a definition.

## 4. Architecture

### 4.1 Pipeline

```
Collect (exists)  every 3 h   stars for the whole watchlist      -> data branch
   |
Analyse           after each Collect
   signals        Hacker News links, scouts' stars                -> signals/
   detect         acceleration, stages, first-flag times          -> detect/
   enrich         details for candidates only                     -> details/
   quality        junk filter, inflation flag, quality score      -> detect/
   judge          Claude: summary, substance, fit                 -> judge/
   |
X-ray             daily + on demand (owner only)
   fetch, parse, agent, validate                                  -> xray/
   |
Site              after Analyse or X-ray, and on pushes to site/
   build-data     data branch -> site/data/*.json
   hugo           -> GitHub Pages
   digest         one GitHub issue per day
```

Each stage is a subcommand of `python -m radar`, reads files, writes files, and
can be run alone against a checkout of the data branch. No stage imports
another stage's internals; they meet only at the contracts in section 6.

### 4.2 Repository layout (target)

```
radar/
  github.py  store.py  collect.py  cli.py        exist
  config.py            all tunable constants, one place
  signals.py           Hacker News and scouts
  detect.py            growth, acceleration, stages, flags
  enrich.py            details for candidate repos
  quality.py           junk filter, inflation, quality score
  ai/
    client.py          the only module that talks to the model API
    judge.py           summary, substance, fit
    budget.py          daily spending guard
  xray/
    fetch.py           safe download and extraction
    parse_python.py    imports, symbols, entry points
    parse_manifest.py  external dependencies
    graph.py           the graph model and its JSON form
    agent.py           the model loop with read-only tools
    validate.py        rejects claims that the graph does not support
    trust.py           trust panel and injection scan
  sitedata.py          builds site/data from the data branch
  digest.py            daily digest text
site/                  Hugo project
profile/               interests.md, scouts.txt
tests/                 one test module per radar module, fixtures/
scripts/               capture scripts, one-off analysis
.github/workflows/     collect.yml (exists), analyse.yml, xray.yml, site.yml, checks.yml (exists)
docs/                  PLAN.md, SPEC.md, DECISIONS.md, ITERATIONS.md
.agent/                briefs and reports for agent runs (git-ignored)
```

### 4.3 Dependencies allowed

| Module | May use | Why |
|---|---|---|
| `radar/ai/*`, `radar/xray/agent.py` | The official `anthropic` Python SDK | Model calls |
| `radar/xray/parse_*` | Standard library (`ast`, `tomllib`, `json`) | Python parsing needs nothing else |
| Site | Hugo extended; one graph library and one chart approach, vendored into `site/assets/` | No CDN, so the site works offline in a demo |
| Everything else | Standard library | Nothing to break in a scheduled job |

Before writing any code that calls the model API, read the current official
documentation (the `claude-api` skill in Claude Code, or the docs lookup tool).
Do not write model IDs, parameters or prices from memory. Record what you
verified in `docs/DECISIONS.md`.

### 4.4 Workflows

| Workflow | Trigger | Permissions | Notes |
|---|---|---|---|
| `collect.yml` | cron every 3 h, manual | `contents: write` | Exists. Change its concurrency group to `data-write` |
| `analyse.yml` | `workflow_run` of Collect (completed), manual | `contents: write` | Runs even if Collect failed, on the data that exists. Needs the model API key secret for the judge step only |
| `xray.yml` | cron daily, manual with `repo` input | `contents: write` | Manual runs only for the repository owner (`if: github.actor == github.repository_owner`) |
| `site.yml` | `workflow_run` of Analyse or X-ray, push to `main` touching `site/**`, manual | `contents: read`, `pages: write`, `id-token: write`, `issues: write` | Build, deploy, digest |
| `checks.yml` | push, pull request | `contents: read` | Exists. Add a Hugo build once the site exists |

Rules for all of them: one shared concurrency group `data-write` for every job
that pushes to the data branch; `git pull --rebase` before `git push`;
third-party actions pinned to a commit SHA; no secret in any job that checks
out or processes repository content it does not need the secret for; the
commit step uses `if: always()` and the job still fails when a stage failed.

## 5. How the lead works

### 5.1 Roles

| Role | Does | Model tier |
|---|---|---|
| **Lead** | Owns this spec, the order of work, the contracts, the merge and the owner conversation. Reviews every diff. Builds or directly supervises anything visual | The strongest available model |
| **Builder** subagent | Implements one work package in its own worktree, from a brief file | A strong coding model; the strongest for WP8 and WP9 |
| **Scout** subagent (`scout`, `Explore`) | Read-only lookups: docs, API behaviour, where something is in the code | A cheap model |
| **Verifier** subagent (`verifier`) | Fresh-context check of a finished work package against its "done when" list. Tries to refute it. Never fixes | A strong model |
| **Owner** | Decides product questions, adds secrets, approves anything outward-facing | |

### 5.2 The loop for one work package

1. **Brief.** The lead writes `.agent/briefs/WP-NN.md`: the goal, the exact
   section numbers of this spec to read, the files the builder owns, the
   contracts it reads and writes, and the "done when" list. The brief is
   handed over as a file path. Never paste specs, diffs or earlier reports
   into a prompt.
2. **Spike.** The builder runs the real upstream system first and saves the
   captures as fixtures. If the spike contradicts this spec, the builder stops
   and reports; the lead updates the spec before any code is written.
3. **Build** on a branch `wp/NN-short-name`, in a separate worktree. Tests in
   the same change. No file outside the brief's owned list is edited; if one
   must be, the builder reports it instead.
4. **Report.** The builder returns one verdict line (`DONE`, `BLOCKED: ...` or
   `OPEN CHOICE: ...`) and writes detail to `.agent/reports/WP-NN.md`:
   what was built, what the spike found, what was *not* done, every command run
   with its real result.
5. **Verify.** A verifier in a fresh context gets the brief path and the
   branch. It runs the tests, runs the stage on real data, and answers the
   review questions in 5.4. Verdict line back, detail in a file.
6. **Fix** what the verifier found, with a test for each defect.
7. **Merge.** The lead reads the whole diff, runs the stage once on a real
   checkout of the data branch, opens a pull request, waits for Checks, merges.
8. **Prove it in production.** For a scheduled stage: trigger the workflow,
   wait for exit code 0, confirm the new output file on the data branch and
   its timestamp. Registered is not delivered.
9. **Log.** One entry in `docs/ITERATIONS.md` (what was tried, what failed,
   what changed) and one line per choice in `docs/DECISIONS.md`.

### 5.3 What runs in parallel

Two builders never own the same file. The lead decides the contract first,
then starts the builders.

| Phase | In parallel | Then |
|---|---|---|
| M1 | WP0 (watchlist, schedule) first and alone. Then WP1 (detect) and WP2 (enrich, quality) | WP3 (site), on their real output |
| M2 | WP4 (signals) and WP5 (judge); WP7 (parser) can start now, it touches nothing else | WP6 (digest, health) |
| M3 | WP8 (agent, validator) after WP7 | WP9 (X-ray pages), on real X-ray files |
| M4 | WP10 (trust, injection) and WP11 (scoreboard, how-it-works) | |
| M5 | WP12 (freeze) | |

Work one or two files wide (a constant, a template fix) is done by the lead
directly. Subagents are for work with seams.

### 5.4 Review questions

Every verifier and every lead review asks:

- For each new test: which production line breaks it?
- Can an unexpected shape (a `null`, a missing key, an empty list, a string
  where a number was expected) crash the stage before it stores anything?
- Can any text from a watched repository reach a query string, a shell command,
  a file path, raw HTML, or a prompt outside the marked data block?
- Does the stage behave the same on Windows and Linux (encodings, newlines,
  path separators, time zones)?
- If this stage is killed halfway, can the next run start?
- Would this assertion also pass against the code before the change?

### 5.5 Whole-system reviews

Per-task review cannot see defects that live between stages. Run one review of
the whole repository **after M2 and at M5**, by a verifier with no build
history, reading the pipeline end to end on real data. It is the single most
valuable review; do not skip it under time pressure.

### 5.6 Screens

A screen can pass every text assertion and still be wrong. For WP3, WP9 and
WP11:

- The agent that builds a screen must be able to *see* it: start the Hugo
  server, take screenshots at desktop and phone width, at rest and scrolled,
  in light and dark, and look at them before reporting.
- The lead shows the owner screenshots for the first version of each screen
  and for any choice between layouts.
- Shared layout parts get a geometry test (bounding boxes do not overlap, the
  header does not cover the first row).
- Real data only in screenshots. A page that looks right with five sample
  cards and breaks with a 90-character repository name is not done.

### 5.7 Approvals the lead needs from the owner once

Ask at the start, in one message, and record the answer in
`docs/DECISIONS.md`:

1. Opening and merging pull requests in this repository.
2. Enabling GitHub Pages with "GitHub Actions" as the source.
3. The owner adds the model API key as a repository secret (the lead never
   handles the key).
4. Installing Hugo on the owner's PC for local preview.
5. The daily budget numbers in `radar/config.py` (section 6.9).

Anything outward-facing beyond these (a custom domain, posting about the
project, publishing a poisoned test repository) is asked separately.

---

## 6. Contracts

The seams between stages. A builder may change the *inside* of a stage freely.
A contract changes only through the lead, and then in this file first.

All files are UTF-8 with `\n` newlines. JSON Lines files hold one object per
line. Times are UTC, `YYYY-MM-DDTHH:MM:SSZ`. Readers skip lines that are not
valid JSON objects and ignore unknown keys. Paths are relative to the data
branch root.

### 6.1 Existing (do not change)

```
repos.jsonl                 {"id","name","created_at","first_seen","source",
                             "stars_at_first_seen","language","license","fork","description"}
snapshots/Y/M/D/HHMMSSZ.jsonl.gz   {"id","stars","forks","pushed_at"}      one line per repo
trending/YYYY-MM.jsonl      {"ts","rank","name","stars_today","id"}        id may be null
gone.jsonl                  {"id","ts"}
runs.jsonl                  one object per collector run, with "ok" and "errors"
```

`id` is GitHub's GraphQL node id and is the key everywhere. `name` is
`owner/repo` as first seen; repositories get renamed, so never join on name.
`source` is `search-new`, `trending`, `refresh`, and after WP4 also `hn` and
`scout`.

### 6.2 Signals (WP4)

```
signals/hn/YYYY-MM.jsonl      {"ts","hn_id","repo","id","title","points","comments","posted_at"}
signals/scouts/YYYY-MM.jsonl  {"ts","scout","repo","id","starred_at"}
```

`repo` is `owner/repo` parsed from the URL; `id` is filled when the repo is
resolved. A Hacker News story is written again when its points change by more
than 20%, so its rise is visible. Unknown repos named by a signal are added to
`repos.jsonl` through the collector's existing lookup path, with the matching
`source`.

### 6.3 Detection (WP1)

```
detect/latest.json          the full current ranking, rewritten each run (the one non-append file)
detect/flags.jsonl          append-only: {"id","name","flagged_at","stage","stars","gain_24h",
                                          "baseline","acceleration","reason"}
detect/runs.jsonl           one summary per run
```

`detect/latest.json`:

```json
{
  "generated_at": "2026-11-14T21:17:40Z",
  "snapshot": "snapshots/2026/11/14/211740Z.jsonl.gz",
  "history_hours": 27.0,
  "repos": [
    {
      "id": "R_kgDO...", "name": "owner/repo",
      "stars": 412, "forks": 31,
      "gain_3h": 44, "gain_24h": 260, "gain_72h": null, "gain_7d": null,
      "baseline": 21.7, "acceleration": 9.7,
      "stage": "rising", "breakout": true, "consecutive_runs": 3,
      "first_flagged_at": "2026-11-14T15:17:40Z",
      "reached_trending_at": null,
      "series": [[ "2026-11-13T18:17:40Z", 152 ], [ "2026-11-14T21:17:40Z", 412 ]]
    }
  ]
}
```

- Snapshots arrive at uneven intervals (2.1), so growth is a **rate**, not a
  difference between two fixed times. `gain_24h` is the star gain per 24 hours
  over the most recent window of `MIN_WINDOW_HOURS` to `MAX_WINDOW_HOURS`: the
  newest snapshot against the snapshot closest to 24 hours before it. Each repo
  entry also carries `window_hours`, the real length of that window.
- A gain is `null` when no snapshot pair fits its window. Never substitute zero
  for "unknown".
- `series` is at most 60 points, for the sparkline.
- `repos` holds every repo with `gain_24h` at or above the minimum gain, not
  only breakouts, sorted by acceleration.
- `detect/flags.jsonl` gets exactly one line per repo, the first time it
  becomes a breakout. It is the evidence for lead time and is never edited.

### 6.4 Details and quality (WP2)

```
details/<id-safe>.json      one file per candidate repo, rewritten when refreshed
```

`<id-safe>` is the node id with every character outside `[A-Za-z0-9_-]`
replaced by `_`.

```json
{
  "id": "R_kgDO...", "name": "owner/repo", "fetched_at": "...",
  "topics": ["bicep"], "homepage": "https://...", "open_issues": 12,
  "default_branch": "main", "disk_kb": 840,
  "contributors": 4, "commits_30d": 57, "releases": 2, "latest_release_at": "...",
  "has_ci": true, "has_tests": true, "has_license": true,
  "manifest_files": ["pyproject.toml"],
  "readme": {"path": "README.md", "chars": 6120, "sha256": "...", "excerpt": "first 6,000 characters"},
  "tree_summary": {"files": 131, "by_extension": {".py": 88, ".md": 9}},
  "junk": {"is_junk": false, "reasons": []},
  "inflation": {"suspect": false, "fork_ratio": 0.08, "reasons": []},
  "quality": {"score": 71, "parts": {"activity": 18, "people": 12, "hygiene": 21, "docs": 20}}
}
```

- Only repos in `detect/latest.json` above the candidate threshold are
  enriched, at most `ENRICH_PER_RUN` per run, least recently fetched first.
- The quality score is arithmetic over the listed parts, documented in
  `radar/quality.py`, so every number on a card can be explained.
- `junk.reasons` and `inflation.reasons` are fixed codes
  (`fork`, `archived`, `awesome-list`, `course-material`, `no-code`,
  `fork-ratio-high`, `stars-in-one-step`, ...), not free text.

### 6.5 Judge (WP5)

```
judge/<id-safe>.json
judge/runs.jsonl            one line per run: calls, tokens in/out, cost estimate, refusals, errors
```

```json
{
  "id": "R_kgDO...", "name": "owner/repo", "judged_at": "...",
  "model": "<exact model id used>", "prompt_version": 3,
  "input_sha256": "<hash of README excerpt + description + profile version>",
  "summary": "One sentence, at most 160 characters.",
  "category": "developer-tool",
  "substance": "real-tool",
  "novelty": "One sentence on what is new, or null.",
  "fit": 82, "fit_reason": "One sentence naming the profile interest it matches.",
  "injection_suspected": false,
  "usage": {"input_tokens": 1840, "output_tokens": 120}
}
```

- `substance` is one of `real-tool`, `library`, `thin-wrapper`, `demo`,
  `list-or-docs`, `hype`, `unclear`. `category` comes from a fixed list in
  `radar/config.py`.
- A repo is judged again only when `input_sha256` changes or `prompt_version`
  rises. This cache is what keeps the cost low.
- The schema is enforced by the API's structured output *and* re-checked by
  code. A response that fails the check is stored as an error, not shown.
- Text fields are plain text. The site escapes them; the judge strips control
  characters and anything that looks like markup.

### 6.6 X-ray (WP7, WP8, WP10)

```
xray/<owner>__<repo>/graph.json      from the parser. Facts.
xray/<owner>__<repo>/xray.json       from the agent, after validation. Meaning.
xray/<owner>__<repo>/trust.json      from the trust panel.
xray/<owner>__<repo>/meta.json       commit sha, times, token use, rejected-claim count
xray/runs.jsonl
```

Directory names use the same character rule as `<id-safe>`, applied to owner
and repo separately.

`graph.json`:

```json
{
  "repo": "owner/repo", "commit": "<sha>", "parsed_at": "...",
  "languages": {"Python": 88},
  "files": [
    {"path": "app/api.py", "lines": 210, "kind": "source",
     "defines": [{"name": "create_app", "type": "function", "line": 14}],
     "entry_point": "fastapi-app"}
  ],
  "edges": [
    {"from": "app/api.py", "to": "app/auth.py", "kind": "import",
     "symbols": [{"name": "verify_token", "type": "function", "used_at": [48, 91]}]}
  ],
  "external": [
    {"name": "fastapi", "declared_in": "pyproject.toml", "spec": ">=0.110",
     "imported_by": ["app/api.py"], "group": "runtime"}
  ],
  "unresolved": [{"file": "app/x.py", "line": 3, "import": "plugins.*", "why": "dynamic"}],
  "limits": {"files_seen": 131, "files_parsed": 88, "truncated": false}
}
```

- An edge exists only when an import resolves to a file in the repository.
  What cannot be resolved goes to `unresolved`, with the reason. Never guess.
- `symbols` lists the names imported across the edge and the lines where the
  importing file uses them. `import module` followed by `module.func()` counts
  as using `func`.
- `entry_point` is set by rules (a `__main__` block, a console script in the
  manifest, a known app object), each rule named in the value.

`xray.json`:

```json
{
  "repo": "owner/repo", "commit": "<sha>", "model": "<id>", "prompt_version": 1,
  "overview": {"what_it_is": "...", "stack": ["Python", "FastAPI"],
               "how_to_run": "...", "entry_points": ["app/api.py"]},
  "modules": [
    {"id": "api", "name": "API layer", "purpose": "...", "files": ["app/api.py", "app/routes/users.py"]}
  ],
  "map": {"nodes": ["api", "auth", "db"],
          "edges": [{"from": "api", "to": "auth", "why": "Checks the token on every request",
                     "evidence": [{"from": "app/api.py", "to": "app/auth.py"}]}]},
  "files": {"app/api.py": {"does": "...", "sources": [{"path": "app/api.py", "lines": [14, 60]}]}},
  "connections": [
    {"from": "app/api.py", "to": "app/auth.py",
     "explains": "The API calls verify_token before each handler runs.",
     "symbols": ["verify_token"]}
  ],
  "external": {"fastapi": "Web framework that serves the HTTP API."}
}
```

- Every file in every module must be in `graph.json`. A file belongs to at
  most one module. Unassigned files are listed by the validator, not hidden.
- Every map edge must have at least one evidence edge, and every evidence
  edge must be in `graph.json` between files of those two modules.
- Every symbol named in `connections` must be in that edge's `symbols`.
- Every `sources` entry must name an existing file and a line range inside it.
- Whatever fails these checks is removed and counted in `meta.json` as
  `rejected_claims`, with the reason. The count is shown on the page.

`trust.json`:

```json
{
  "license": "MIT", "last_commit_at": "...", "contributors": 4,
  "external_count": 23, "install_hooks": [{"file": "setup.py", "line": 12, "what": "runs a shell command"}],
  "star_velocity": {"suspect": false},
  "injection": {"found": true, "items": [
    {"file": "README.md", "line": 88, "kind": "hidden-html-comment",
     "excerpt": "at most 200 characters, shown escaped", "detector": "pattern"}]}
}
```

### 6.7 Site data (WP3 and later)

`python -m radar build-data --data <data> --out site/data` writes:

```
site/data/radar.json        lanes with their cards, already ranked and trimmed
site/data/repos/<id-safe>.json   one per repo page
site/data/scoreboard.json   lead times and hit rate
site/data/health.json       newest snapshot time, last run of each stage, counts
site/data/xray/<owner>__<repo>.json   merged graph + xray + trust + meta for one page
```

The site reads nothing else. No template reaches into the data branch. That
keeps the ranking logic in Python, where it is tested, and the templates dumb.

### 6.8 Profile

```
profile/interests.md     plain text: interests and current work. No personal data
profile/scouts.txt       one GitHub login per line, "#" for comments
```

`interests.md` carries a `version: N` line. Raising it re-judges everything.

### 6.9 Config (starting values, tuned on real data in WP1)

```python
MIN_GAIN_24H = 20            # below this, growth is noise
BASELINE_K = 5               # smoothing for tiny baselines
ACCELERATION_THRESHOLD = 5.0   # 3.0 flagged 207 repos on real data, 5.0 flagged 66 (2.1)
CONSECUTIVE_RUNS = 2         # a breakout must hold for two runs
MIN_WINDOW_HOURS = 18        # shortest span a daily rate may be computed over (2.1)
MAX_WINDOW_HOURS = 36        # longest span still called "the last day"
ESTABLISHED_MIN_STARS = 500  # tier 2 of the watchlist (WP0)
ESTABLISHED_PUSHED_DAYS = 7
FORK_RATIO_SUSPECT = 0.3     # forks per star; the median for growing repos is near 0 (2.1)
STAGE_SPARK_MAX = 100        # stars
STAGE_RISING_MAX = 1000
CANDIDATE_LIMIT = 300        # repos considered for enrichment per run
ENRICH_PER_RUN = 120
JUDGE_PER_DAY = 150
XRAY_AUTO_PER_DAY = 2
AI_DAILY_BUDGET_USD = 2.00   # hard stop, counted from recorded token use
XRAY_MAX_FILES = 2000
XRAY_MAX_BYTES = 30_000_000
XRAY_MAX_FILE_BYTES = 400_000
XRAY_AGENT_MAX_TOOL_CALLS = 40
```

---

## 7. Work packages

Each one names its goal, what it owns, what it must do, and when it is done.
"Done when" is the acceptance test; a package that meets it is finished even
if more could be added.

### WP0 - Watch established repos, and make the schedule dependable  (M1, first)

**Goal:** close the two gaps the first data exposed (2.1): the radar must see
established repos before they trend, and it must run often enough to matter.

**Owns:** `radar/collect.py`, `radar/config.py`, `tests/test_collect.py`,
`.github/workflows/collect.yml`, `scripts/capture_fixtures.py`.
**Reads and writes:** 6.1 (no shape change; `source` gains `search-established`).

**Spike first:** time a full sweep of the established tier (star-range slices
that each stay under 1,000 results; find the slice boundaries from real
counts). Time a refresh of 45,000 repos in batches of 100 and note the
rate-limit cost inside Actions. Look at a week of `runs.jsonl` and measure how
late and how often the schedule really fires.

**Must:**

- **Tier 2 discovery:** repos with `ESTABLISHED_MIN_STARS` or more stars pushed
  in the last `ESTABLISHED_PUSHED_DAYS` days, found by star-range slices, once
  a day (not every run). They join `repos.jsonl` with source
  `search-established` and are refreshed like every other watched repo.
- **Truncated day slices** (more than 1,000 results) are split by star range
  the same way, so the lowest-star tail is no longer lost.
- **Retire quiet repos from frequent refresh:** a repo with no star change for
  14 days is refreshed once a day; this needs only the registry and a small
  `watch/state.json` cache, rewritten each run. Document it as the second
  non-append file.
- **A run must finish inside 15 minutes** and inside the Actions rate limit
  with room to spare; record both in `runs.jsonl`.
- **Schedule:** change the cron to hourly and make the collector skip (exit 0,
  one log line, no snapshot) when the newest snapshot is younger than
  2.5 hours. A late or dropped trigger then costs at most an hour instead of a
  whole cycle.
- **Second trigger:** a hidden scheduled task on the owner's PC that starts the
  workflow (`gh workflow run`) every 3 hours while the PC is on. It is a
  backup, not the main path; the skip rule makes double triggers harmless.
  Installing it needs the owner's go-ahead.

**Done when:** a week of `runs.jsonl` shows no gap longer than 4 hours while
the owner's PC was on and none longer than 6 otherwise; at least 15 of the
next 20 repos that appear on Trending were on the watchlist beforehand; run
time and rate cost are recorded; the skip rule has a test.

### WP1 - Detect and lead time  (M1)

**Goal:** turn snapshots into a ranking by acceleration, and record the moment
each repo is first flagged.

**Owns:** `radar/detect.py`, `radar/config.py`, `tests/test_detect.py`, the
`detect` subcommand.
**Reads:** 6.1. **Writes:** 6.3.

**Spike first:** check out the data branch and look at real growth. How many
repos gain 20 or more stars in 24 hours? What does the distribution of
acceleration look like? Which of today's Trending repos would the starting
constants have flagged, and when? Write the answers into the report with the
numbers; they set the constants in 6.9.

**Must:**

- Load only the snapshots it needs (the newest, the previous one, and the
  ones closest to 24 hours, 72 hours, 7 days and 8 days back), not the whole
  history. Work in rates over the real window lengths (6.3).
- `baseline`: average daily gain over the 7 days before the last 24 hours.
  When that history does not exist yet, use the repo's lifetime average up to
  24 hours ago, from `created_at`. Record which one was used.
- `acceleration = gain_24h / (baseline + BASELINE_K)`.
- A breakout needs `gain_24h >= MIN_GAIN_24H`, acceleration at or above the
  threshold, and both for `CONSECUTIVE_RUNS` runs in a row.
- Stage from current stars: spark, rising, large. `mainstream` once the repo
  has appeared in `trending/`.
- `reached_trending_at` is the first `ts` in `trending/` for that id (match by
  id, fall back to case-insensitive name for rows whose id is null).
- Survive gaps: missed runs (they are normal, see 2.1), a repo absent from one
  snapshot, a star count that goes *down* (7% of repos in two days), a repo
  that was renamed.
- The first test cases are the real early catches and the real Trending repos
  named in 2.1.
- With less than 24 hours of history, write `detect/latest.json` with an empty
  `repos` list and `history_hours` set, and exit 0. That is a valid state.

**Done when:**

- Tests replay real snapshot files copied from the data branch (a trimmed set
  of real repos, not invented rows) and cover: a known riser is flagged, a
  flat repo is not, a one-run spike is not, a gap of two missed runs, a falling
  count, less than 24 hours of history.
- Running it twice on the same data appends no second line to `flags.jsonl`.
- It runs on the full real data branch in under 60 seconds.
- The report lists the ten top breakouts from real data, and the lead has
  looked at each on GitHub and judged whether flagging it is reasonable.

### WP2 - Enrich and quality  (M1)

**Goal:** fetch the details of candidate repos only, remove junk, flag
inflated stars, compute an explainable quality score.

**Owns:** `radar/enrich.py`, `radar/quality.py`, their tests, the `enrich`
subcommand.
**Reads:** 6.1, 6.3. **Writes:** 6.4.

**Spike first:** for 20 real candidates, time the GraphQL call with every
field in 6.4, and capture the real responses. Find out what a missing README,
an empty repo and a 404 look like. Decide from the timings whether details are
fetched one repo per call or in small batches.

**Must:**

- Fetch only what 6.4 lists. README: the default-branch README, any casing or
  extension, capped at the excerpt length; store its hash.
- Detect junk and inflation by rules with fixed reason codes. Every rule has a
  test with a real repository of that kind, captured as a fixture.
- Two inflation rules come straight from the data (2.1): `same-name-cluster`
  (three or more watched repos share a repository name and show the same star
  gain in the same interval) and `fork-ratio-high` (forks per star above
  `FORK_RATIO_SUSPECT`). The `ai-manus` cluster is the fixture for the first.
- Repos flagged as inflated are not deleted. They leave the lanes and are
  listed on the site under "Hidden as fake growth", with the rules that fired.
- Compute `quality.score` as documented arithmetic. No model call.
- Respect `ENRICH_PER_RUN`, and refresh the least recently fetched first.
- Treat every fetched string as untrusted (rule 5).

**Done when:**

- A run on real candidates writes a valid details file for each, and a repo
  that 404s or has no README does not fail the run.
- The lead has checked the junk and inflation flags for 20 real repos by hand;
  wrong flags are either fixed or listed as known limits.
- The score for one repo can be recomputed by hand from its details file.

### WP3 - The site: Radar, repo pages, scoreboard shell  (M1)

**Goal:** the public dashboard, live on GitHub Pages, built from real data.

**Owns:** `site/**`, `radar/sitedata.py`, `tests/test_sitedata.py`,
`.github/workflows/site.yml`, the Hugo step in `checks.yml`.
**Reads:** 6.3, 6.4, later 6.5. **Writes:** 6.7.

**Spike first:** install Hugo; generate 500 repo pages from JSON with a content
adapter and time the build; confirm the Pages deploy with an empty site before
designing anything. Capture a real `radar.json` from WP1 and WP2 output and
design against it.

**Must:**

- **Radar (home).** Lanes: *Breaking out* (all of GitHub) and, once WP5 exists,
  *For you*; later *Just discussed* and *Scouts' picks*. A lane is a ranked
  list of cards.
- **Card.** Repo name, one-line description (the AI summary when it exists,
  otherwise GitHub's), language, stage badge, stars, gain in 24 h, a sparkline
  from `series`, quality score, fit score when it exists, the reason, "first
  flagged N hours ago", and a marker when it has reached Trending.
- **Repo page.** Growth chart since first sighting, with the flag moment and
  the Trending moment marked; the signals that fired; the quality parts; junk
  and inflation flags in words; links to GitHub and to the X-ray when present.
- **Scoreboard (shell).** The table and the headline numbers, from
  `scoreboard.json`, honest about small samples ("3 repos so far"), and with
  the misses and their reasons next to the hits from the first version on.
- **Hidden as fake growth:** a section listing what the inflation rules
  removed, with the rules that fired.
- **Health footer** on every page: "data updated at", from `health.json`, and
  a visible warning when it is older than 7 hours.
- "New since your last visit" from the browser's local storage, with the page
  fully usable when storage is unavailable.
- Filters on the Radar by language, category and stage, working without a
  server.
- Readable at phone width and on a projector, light and dark, keyboard
  reachable, text contrast that passes WCAG AA.
- All repository text escaped. Links to repositories built from the validated
  `owner/repo` only.
- Empty states designed, not accidental: no breakouts yet, no history yet.

**Mockups:** five screens exist as a design canvas (the owner has the link;
it is private): Radar A (three lanes side by side), Radar B (one ranked table
with tabs and filters), the repo page, the X-ray page and the scoreboard. They
use real data from 13-15 Nov. **The owner chose Radar A (three lanes) on
15 Nov.** Build the home page from `docs/mockups/Main.dc.html`. Radar B's
sortable table is not built; its filters (stage, language, not on Trending,
new since last visit) are kept on Radar A. The other screens are the starting
point, not a pixel contract.

**Design direction:** this is a tool people scan, not a marketing page. Dense,
calm, legible. The growth line is the hero of every card. Use the
`frontend-design` guidance for a distinct look; follow section 5.6 for
screenshots. Bring the owner two layout options for the Radar before building
the second screen.

**Done when:**

- The site is live on Pages and rebuilt automatically after an Analyse run.
- `build-data` has tests on real stage output, including a repo with a
  90-character name, a description full of HTML and emoji, and a repo with no
  details file yet.
- Screenshots (desktop, phone, light, dark) are in the report and the lead has
  looked at every one.
- Hugo builds in Checks, and a broken template fails the pull request.

### WP4 - Early signals: Hacker News and scouts  (M2)

**Goal:** find repos through people before the star counts move.

**Owns:** `radar/signals.py`, its tests, the `signals` subcommand,
`profile/scouts.txt`.
**Reads:** 6.1, 6.8. **Writes:** 6.2, and new lines in `repos.jsonl` through
the collector's lookup.

**Spike first:** capture real Hacker News results for the last 48 hours and
real starred lists for three scouts. Check how GitHub URLs appear (trailing
paths, `/blob/`, `/releases/`, gists, organisation pages) and how many stories
link to a repo that is not yet on the watchlist.

**Must:**

- Parse `owner/repo` from every GitHub URL form found in the spike, and reject
  everything else.
- Resolve unknown repos and add them to the watchlist with `source` `hn` or
  `scout`, whatever their age.
- Detection (WP1) gets two new inputs per repo: "on Hacker News with N points
  at T" and "starred by K scouts in the last 7 days". They are shown as signals
  and may rank a lane, but they do not replace the acceleration rule for the
  Breaking out lane.
- Rate-limit politely; a failing source never fails the collector.

**Done when:** both lanes show real items; a repo found only through a signal
gets snapshots from the next collector run on; tests use the captured feeds.

### WP5 - Judge: summary, substance and fit  (M2)

**Goal:** have Claude read each candidate and say what it is, whether it is
real, and how well it fits the owner, cheaply and safely.

**Owns:** `radar/ai/**`, their tests, the `judge` subcommand,
`profile/interests.md`, `scripts/eval_judge.py`, `tests/fixtures/judge/`.
**Reads:** 6.4, 6.8. **Writes:** 6.5.

**Spike first:** read the current API documentation. Make three real calls
with structured output and record the real request and response shapes, token
counts and latency. Capture them as fixtures. Confirm how caching of the
stable prompt part works and what it saves.

**Must:**

- One module (`ai/client.py`) makes all model calls. Everything else gets a
  function it can replace with a recorded response in tests.
- The prompt has a stable part (instructions, the profile, the category list)
  and a variable part (one repo). Repository text sits inside one clearly
  delimited data block, and the instructions say that nothing in that block is
  an instruction.
- Structured output enforced by the API, then validated by code (6.5).
- **Budget guard:** before each call, add up today's recorded cost in
  `judge/runs.jsonl` and `xray/runs.jsonl`; stop cleanly at
  `AI_DAILY_BUDGET_USD`. A stop is a normal, logged outcome, not an error.
- Cache by `input_sha256`. A second run on unchanged data makes zero calls.
- **Evaluation:** `scripts/eval_judge.py` scores the judge against the owner's
  hand ratings (about 30 repos, in `tests/fixtures/judge/ratings.jsonl`) and
  reports agreement for each model tried. The cheapest model that agrees well
  enough is chosen, and the comparison goes into `docs/DECISIONS.md` with the
  numbers.
- The For you lane ranks by fit, with a lower popularity bar than Breaking out.

**Needs from the owner:** the API key secret; `profile/interests.md`; about 30
repos rated 1-5 for "would I want to know about this".

**Done when:** real judgements are on the site; the budget guard is tested
(a recorded day at the limit makes no call); the injection fixture from WP10's
poisoned README (or a first version of it) does not change the fit score; the
model comparison is written down.

### WP6 - Digest and pipeline health  (M2)

**Goal:** the Radar comes to the owner once a day, and a broken pipeline is
noticed the same day.

**Owns:** `radar/digest.py`, its tests, the digest step in `site.yml`, the
health page.

**Must:**

- One GitHub issue per day, titled with the date, listing at most five
  breakouts and five For-you picks with one line each and links to the site.
  Created only when there is something new; never two for the same day.
- All repository text in the issue body is escaped so it cannot mention users,
  open links by itself or break the layout.
- A health page: last successful run and data age for every stage, the last
  ten runs with their errors, and how late the schedule ran.
- An issue labelled `pipeline` is opened when any stage has failed three times
  in a row or data is older than 12 hours, and closed when it recovers.

**Done when:** a real digest issue exists and reached the owner's inbox; a
forced failure opens the pipeline issue and a good run closes it.

### Review R1 - whole system, after M2

See 5.5. Output: a list of cross-stage defects, each fixed with a test before
M3 work merges.

### WP7 - X-ray facts: fetch and parse  (M3; can start during M2)

**Goal:** from a repository URL to a true graph of its Python code.

**Owns:** `radar/xray/fetch.py`, `parse_python.py`, `parse_manifest.py`,
`graph.py`, their tests, `tests/fixtures/xray/`.
**Writes:** `graph.json` (6.6).

**Spike first:** pick five real Python repositories of different shapes (a
flat script collection, a `src/` layout package, a Django or FastAPI app, a
monorepo with two packages, one with heavy relative imports). Parse them and
check twenty edges of each by hand against the source. Record every import form
the parser got wrong.

**Must:**

- **Fetch safely.** Download the tarball for a named commit; enforce
  `XRAY_MAX_BYTES`, `XRAY_MAX_FILES`, `XRAY_MAX_FILE_BYTES`; refuse entries
  with absolute paths, `..`, symlinks or device files; extract only into a
  fresh temporary directory; never run, import or install anything from it.
- **Resolve imports** to files: absolute, relative (`.`, `..`), packages
  (`__init__.py`), `src/` layouts, namespace packages. What does not resolve
  is external or `unresolved`, never a guessed edge.
- **Symbols on edges:** `from a import b`, `import a` then `a.b`, aliases,
  re-exports through `__init__.py` (follow one level and say so).
- **External dependencies** from `pyproject.toml`, `requirements*.txt`,
  `setup.cfg`, `setup.py` (read as text with `ast`, never executed), matched to
  the imports that use them.
- **Entry points** by named rules.
- A file with a syntax error is recorded as unparsed and does not stop the run.
- Deterministic output: the same commit gives byte-identical `graph.json`.

**Done when:** for the five spike repositories, at least 95% of hand-checked
edges are right and no edge is invented; each wrong case is either fixed or
listed under `unresolved` with its reason; the malicious-archive tests
(path traversal, symlink, oversize) pass.

### WP8 - X-ray meaning: agent and validator  (M3)

**Goal:** Claude explains the graph; code makes sure it only says what the
graph supports.

**Owns:** `radar/xray/agent.py`, `validate.py`, their tests, the `xray`
subcommand, `.github/workflows/xray.yml`.
**Reads:** `graph.json`. **Writes:** `xray.json`, `meta.json` (6.6).

**Spike first:** run a minimal tool-use loop on one real graph and record how
many tool calls and tokens a useful answer takes, and what the model gets
wrong. Tune `XRAY_AGENT_MAX_TOOL_CALLS` and the file budget from that.

**Must:**

- **Tools, all read-only, all over the extracted tree:** `get_tree()`,
  `get_graph(module_or_path)`, `read_file(path, start, end)` with a line cap,
  `search_code(text)` with a result cap. Paths are checked against the tree;
  nothing outside it can be read. No network tool, no write tool.
- File content returned by a tool is wrapped as untrusted data, the same way
  as in WP5.
- The agent produces `xray.json` by structured output.
- **The validator is separate code and decides alone.** It applies every rule
  under 6.6, removes what fails, and records each rejection with its reason.
  The model is never asked whether its own answer is right.
- If more than a set share of claims is rejected, the X-ray is marked
  low-confidence and the page says so.
- Budget guard and caching as in WP5: one X-ray per repo per commit.
- `python -m radar xray owner/repo --data <dir>` works locally, and a second
  run for the same commit uses the cache and needs no network. This is the
  live demo path.

**Done when:** three well-known Python repositories have X-rays the owner has
read and judged correct in the main; the rejected-claim count is recorded for
each; a test feeds the validator an answer with an invented file, an invented
edge, a wrong symbol and an out-of-range line reference, and all four are
removed.

### WP9 - X-ray pages  (M3)

**Goal:** make the structure of a codebase understandable in a minute.

**Owns:** the X-ray templates and scripts under `site/`, the X-ray part of
`sitedata.py`.

**Must:**

- **Architecture map:** the modules as 5-8 boxes with labelled arrows. Click a
  box to see its purpose and files.
- **File graph:** interactive, grouped and coloured by module, edges labelled
  with the symbols they carry. Click an edge to read the explanation of that
  connection. Click a file for the file panel. Usable with 300 files: start
  collapsed to modules and expand on demand.
- **File panel:** what the file does, what it defines, what it uses and from
  where, who uses it, with links to the exact lines on GitHub at the parsed
  commit.
- **External dependencies:** grouped by purpose, each with its one-line role
  and the files that import it.
- **Technical overview** and the **trust panel** (from WP10 when it lands).
- A visible line: "Structure parsed from commit `abc1234`. N claims by the AI
  were rejected by the validator." with a link to what that means.
- Everything works without a server and without a CDN.

**Done when:** screenshots per 5.6 for a small and a large repository; the
owner has used the pages for a repository they do not know and can say how it
is built; keyboard navigation reaches every node's information.

### WP10 - Trust panel and injection defence  (M4)

**Goal:** show whether a repository can be trusted, and prove the pipeline
cannot be talked into anything by the code it reads.

**Owns:** `radar/xray/trust.py`, its tests, `tests/fixtures/poisoned/`, the
defence section of the How-it-works page.

**Must:**

- Trust facts by code: licence, activity, contributors, dependency count,
  install hooks (`setup.py` commands, `postinstall`, build scripts that fetch
  and run), star velocity.
- **Injection scan**, two detectors, results kept apart: patterns (text that
  addresses AI agents, hidden HTML comments, zero-width and bidirectional
  control characters, instructions inside image alt text) and one cheap model
  classification call on the README. Found items are shown, escaped, in the
  trust panel.
- **The poisoned fixture:** a small repository of the project's own, kept as a
  local fixture tree, whose README and a code comment try to (a) raise the fit
  score, (b) make the X-ray describe a fake architecture, (c) make the agent
  read a file outside the tree, (d) leak the profile into the output. The
  expected results are recorded from real runs, not written by hand.
- **The demonstration:** the same fixture run twice, once with the defences
  switched off by a test-only flag and once with them on, with both outputs
  stored so the difference can be shown.
- A written threat model on the How-it-works page: what an attacker controls,
  what the worst outcome is with each layer removed, and why the worst case
  with all layers on is a wrong explanation that the validator flags.

**Done when:** all four attacks are shown to succeed or be attempted without
the defences and fail with them; the scan flags the fixture; no test depends on
a lucky model answer (the defence that matters is enforced by code).

Publishing a poisoned repository on GitHub needs the owner's separate
approval. The local fixture is enough for the tests.

### WP11 - Scoreboard and "How it works"  (M4)

**Goal:** the proof, and the explanation.

**Must:**

- **Scoreboard:** for every repo ever flagged: flagged at, stage and stars
  then, reached Trending at (or "not yet"), lead time, stars now. Headline
  numbers: median lead time, share of flagged repos that reached Trending
  within 14 days, share of Trending repos the radar flagged first. Also the
  misses: Trending repos never flagged, with the reason where it can be told
  (not on the watchlist, growth too slow, flagged late).
- Numbers are computed in `sitedata.py` with tests on real data. Sample sizes
  are always shown.
- **How it works:** the pipeline diagram, what is code and what is AI and why,
  the models and the measured cost per day, the judge evaluation, the
  validator, the threat model, the known limits.

**Done when:** every number on the scoreboard can be traced to lines in
`flags.jsonl` and `trending/`; the misses table is not empty by design.

### Review R2 and WP12 - Freeze  (M5)

- Whole-system review (5.5).
- X-rays for three well-known repositories built and cached.
- The local demo rehearsed with the network off: `radar xray` from cache, Hugo
  serving the built site.
- Snapshot thinning: keep every snapshot for 14 days, then one per day. One
  commit, announced in `docs/DECISIONS.md`.
- README rewritten for a visitor: what it is, a screenshot, the scoreboard
  numbers, how it works, how to run it.
- A day-slice fix for discovery if the 1,000-result cap is still losing repos:
  split a truncated day by star range.

### After the freeze (ordered backlog)

1. TypeScript and JavaScript in the X-ray (a real parser, by decision).
2. Explanation levels: beginner, developer, architect.
3. Feedback: thumbs on cards through a prefilled issue, handled by a workflow
   for the owner only, feeding the fit ranking.
4. Embeddings: similar repositories and a pre-filter before the judge.
5. Function-level view inside a file.
6. "Follow a request": an animated path through the code.
7. Compare two repositories.
8. Weekly written report; topic pages; release watching.
9. More sources (Lobsters, Reddit, package registries) and more languages.

---

## 8. Milestones

| Date | Milestone | Packages | Proof |
|---|---|---|---|
| 13 Nov | M0 Collector | done | Runs green, data on the branch. First findings in 2.1 |
| 20 Nov | M1 Radar live | WP0, WP1, WP2, WP3 | Public URL shows real breakouts; established repos are on the watchlist |
| 26 Nov | M2 AI ranking | WP4, WP5, WP6, R1 | For you lane, digest in the inbox, model comparison |
| 3 Dec | M3 X-ray | WP7, WP8, WP9 | Three real X-rays the owner judged correct |
| 8 Dec | M4 Trust and proof | WP10, WP11 | Attack shown with and without defence; scoreboard with real lead times |
| 11 Dec | M5 Freeze | R2, WP12 | Offline demo rehearsed |

If a milestone slips, cut from the end of its package list and from "After the
freeze", never from tests, the validator or the reviews. The order of value
is: the collector keeps running, the Radar is live, the judge works, the X-ray
is true, the proof is shown.

## 9. Risks the lead watches

| Risk | Sign | Response |
|---|---|---|
| Detection is noise | The top ten are star-farmed or already famous | Tune on real data (WP1 spike); lean on inflation flags and the judge's substance |
| Too little history to prove lead time | Few rows in `flags.jsonl` by early December | Keep the collector healthy above all; show sample sizes honestly |
| The X-ray is wrong on a repo someone knows | Hand-checks below 95% | Narrow what is claimed; show `unresolved`; never draw a guessed edge |
| AI cost drifts | `judge/runs.jsonl` cost rising day over day | The budget guard stops it; check the cache hit rate first |
| Schedules pause or lag | Seen on day one: 5 runs in 36 hours (2.1) | Hourly cron with a skip rule and a second trigger (WP0); the health issue (WP6) |
| The radar only sees part of GitHub | A Trending repo that was never on the watchlist | The scoreboard's misses table shows it; widen the tiers (WP0) |
| Data branch grows | Clone time, repository size | Thinning (WP12), earlier if size passes 500 MB |
| A subagent builds on an invented shape | A test passes and the real run fails | Rule 2; the lead runs every stage on real data before merging |
| Scope | A milestone slips twice | Section 8's cutting order; ask the owner what to drop |
