# Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-11-13 | Measure star growth from our own snapshots | GitHub exposes no star history (REST 404, GraphQL empty) and GH Archive now carries about 0.3% of star events |
| 2026-11-13 | GraphQL for discovery and refresh | 100 repos with all needed fields cost 1 rate-limit point |
| 2026-11-13 | One search query per creation day | Search returns at most 1,000 results per query; a single day at 10+ stars is about 650 |
| 2026-11-13 | Plain append-only files on a `data` branch | No server, free hosting, every run is a small reviewable commit, DuckDB can query the files directly |
| 2026-11-13 | Record github.com/trending every run | It is the benchmark; lead time cannot be reconstructed afterwards |
| 2026-11-13 | Standard library only for the collector | Nothing to install, nothing to break in a scheduled job |
| 2026-11-13 | Static Hugo site on GitHub Pages | No backend to run; all AI work happens in the pipeline and is published as data |
| 2026-11-15 | Watch established repos (500+ stars, active in the last 7 days) as a second tier | All 19 repos seen on Trending were older than the 30-day discovery window |
| 2026-11-15 | Hourly cron with a skip rule, plus a backup trigger | GitHub started the 3-hourly schedule only 5 times in 36 hours |
| 2026-11-15 | Growth is a rate over the real interval between snapshots | Intervals were 4 to 9 hours, not 3 |
| 2026-11-15 | Breakout threshold starts at 5x normal pace | 3x flagged 207 repos on real data, 5x flagged 66 |
| 2026-11-15 | Radar home page uses layout A: three lanes side by side | Owner's choice from two mockups; general and personal stay visible together |
| 2026-11-25 | Add a taste loop (WP5b): the judge learns from the owner's ratings, measured round by round | Owner's choice of three options (taste loop, trained breakout predictor, research agent); it serves "find what is interesting to me" directly and reuses the judge |
| 2026-11-25 | Only randomly picked ratings are test data; results carry a 90% interval | The judge's own picks would bias the test set; about 48 test ratings are too few for a point estimate alone |
| 2026-11-25 | Ship established-repo watching and the live detector together, first | Only a running detector issues alerts that count as evidence; both reviews found the old order lost days |
| 2026-11-25 | Lead time is measured from live alerts against the last Trending poll that did not show the repo; replays never count | Trending is polled hours apart, and replayed flags could claim a time nobody saw |
| 2026-11-25 | The scoreboard is built for zero hits; a median is shown only from 5 early alerts; the 14-day hit rate only for alerts 14 days old | Too little time before the freeze for a large sample |
| 2026-11-25 | Each workflow that writes data has its own concurrency group | GitHub cancels a waiting run when a newer one joins the same group |
| 2026-11-25 | X-ray workflow split into parse (no secrets), explain (key, no write) and publish (write, no key) | Untrusted code, the model key and a write token never share a job |
| 2026-11-25 | The validator checks references, not prose; prose is labelled as AI interpretation | A sentence can cite a real edge and still be wrong; the threat model says so |
| 2026-11-25 | Round 0: 50 blind ratings, 20 to choose the model and 30 as a frozen test set; one learning round is Must | Separates model choice from measurement and keeps the owner's load at about 25 minutes. Replaces the earlier rule that random picks in every round are the test set |
| 2026-11-25 | For the freeze the Radar shows two lanes, Breaking out and For you | The third lane (Just discussed) needs Hacker News, which is Could |
| 2026-11-25 | A high fork ratio alone is a caution, not an exclusion | Templates and teaching repos are forked a lot for legitimate reasons |
