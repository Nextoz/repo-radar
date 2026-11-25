# Iterations

What was built, what was tried, what failed and what changed.

## v0 - Collector (13 Nov 2026)

**Goal:** start recording star counts, because growth cannot be measured for
any day that was not recorded.

**Tried and dropped before writing code**

- *GH Archive as the star-event source.* One hourly file held 261 star events;
  the monthly total has fallen from about 6 million (2024) to about 84,000.
  OSS Insight reports the same and has switched its trending ranking off.
- *Star timestamps from the API.* REST returns 404 and GraphQL returns an empty
  list, also for large repos.

**Built**

- Discovery by GraphQL search, one query per creation day for the last 30 days.
- A benchmark recorder for github.com/trending.
- Refresh of watched repos that the search no longer returns.
- Append-only file store on the `data` branch, with a `status` health check.
- Tests on captured API responses.

**Failed first, then fixed**

- The first live run did not finish in 10 minutes. Timing single calls showed
  6-10 seconds each once topics and open-issue counts were requested. Without
  them, and with four calls in parallel, a run takes about 3.5 minutes.
- An independent review in a fresh context failed the first version on five
  points: an unexpected response could crash a run before anything was stored;
  a transient empty answer could retire a live repo for good; a mid-pagination
  failure was untested; a half-written line could block later runs; the health
  check accepted a future-dated snapshot. All fixed, each with a test.

## v0.1 - First look at real data (15 Nov 2026)

No product code. Two days of snapshots were analysed before planning further.

**Found**

- All 19 repos seen on GitHub Trending were older than the 30-day discovery
  window (65 days to 5 years old). None was on the watchlist before it trended.
- GitHub started the 3-hourly schedule only 5 times in 36 hours.
- Growth is rare: the median repo gained nothing; 1% gained 165 stars a day or
  more. A threshold of 3x normal pace flagged 207 repos, 5x flagged 66.
- A star farm: twelve same-named repos with identical star counts moving at
  the same moment, fork ratio about 0.7.
- 7% of repos lost stars between two snapshots.
- Real early catches that were not on Trending, for example a repo going from
  65 to 362 stars.

**Changed**

- The spec gained section 2.1 (the findings) and work package WP0: watch
  established repos, run hourly with a skip rule, add a backup trigger.
- Detection is specified as a rate over the real interval between snapshots.
- Two inflation rules were added from the data.
- Five screen mockups were made from the real data (`docs/mockups/`).

## v0.2 - The taste loop, designed (25 Nov 2026)

No product code. The spec gained a way for the judge to learn what the owner
finds interesting.

**Found**

- After 12 days, 50 different repos had appeared on Trending and none of them
  was on the watchlist beforehand. Watching established repos (WP0) is still
  the first thing to build.
- The scheduled collector ran with a median gap of 8.7 hours.
- The owner's GitHub account has almost no stars, so taste cannot be read
  from it. It has to come from ratings.

**Changed**

- New work package WP5b and contract 6.10: the owner rates batches of 20
  repos; the model proposes a new taste profile from the ratings; the owner
  approves it; rated repos become examples for the judge; each round is
  measured.
- An independent review of the design found 12 problems before any code was
  written. The main ones: a test set partly chosen by the judge itself, old
  profiles that could not be recovered, a cache key that ignored the
  examples, too few test ratings to claim a trend without a range, and
  baselines measured with later star counts. All were fixed in the spec: only
  random picks are test data, every profile version is kept, each
  configuration has its own hash, results carry a 90% interval, and the
  numbers at rating time are frozen with each rating.

## v0.3 - The spec refreshed and reviewed twice (25 Nov 2026)

No product code. The spec was brought up to date, then reviewed by two
independent AI reviewers from different model families (Claude in a fresh
context, and GPT-6.2-Astra through the Codex command line, read-only). One
said "ready with fixes", the other "not ready". Their findings overlapped on
most points.

**Found**

- The order of work lost evidence: watching established repos alone issues
  no alert. Only a running detector does, and days without one cannot be
  recovered.
- The headline claim was stronger than the data can be by the freeze: a
  14-day hit rate needs alerts 14 days old, the Trending time is a poll
  hours apart, and only repos that later trend can have a lead time.
- All writing workflows shared one GitHub concurrency group, where a newer
  waiting run cancels an older one, so the judge could be skipped silently.
- The validator checks references, not prose; the spec had claimed more.
- The X-ray workflow put untrusted code, the model key and a write token in
  one job.
- The taste measurement mixed choosing the model with measuring it, and the
  owner would have rated from the AI's own summary.
- One count was wrong: 35 runs, not 36.

**Changed**

- A live slice first (26 Nov): established repos and the live detector ship
  together; detection and the parser start at once.
- Exact hold rule with replay equal to incremental processing; live alerts
  and replays kept apart; alerts classed early, ambiguous or late against the
  Trending polls; a scoreboard built for zero hits.
- One concurrency group per writer; analysis runs as a second job of the
  collector; the X-ray workflow split into parse, explain and publish jobs.
- Prose shown as labelled AI interpretation, with links, markup and unlisted
  shell commands removed; the agent's tool trace is shown.
- Round 0 is 50 blind ratings: 20 choose the model, 30 are a frozen test
  set; the page reports the paired change between rounds and a keyword
  baseline.
- The injection experiment runs each attack five times per arm and reports
  attempts, effects and blocked actions apart; it passes on code boundaries.
- A Must, Should and Could cut line, firm dates for what waits on the owner,
  and a four-minute demo path that runs offline without Hugo.
- Three mockups were redrawn to match: the Radar with two lanes and an
  exclusion section, a scoreboard built for zero hits with alerts classed
  early, ambiguous or late, and an X-ray page that separates parser-verified
  facts from AI interpretation and shows the agent's tool trace.
