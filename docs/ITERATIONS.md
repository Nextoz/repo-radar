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
