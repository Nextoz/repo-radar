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
