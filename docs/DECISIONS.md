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
