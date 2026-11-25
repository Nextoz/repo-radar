# Mockups

Five screens, drawn before the site was built, using real data collected on
13-15 Nov 2026. Three were updated on 25 Nov 2026 to match the reviewed
`docs/SPEC.md`.

| File | Screen |
|---|---|
| `Main.dc.html` | Radar A, the home page: two lanes (Breaking out, For you), "Excluded by growth heuristics", and the "Many forks" caution. Updated 25 Nov |
| `RadarB.dc.html` | Radar B: one ranked table with tabs and filters. Not chosen; kept for reference |
| `Repo.dc.html` | Repo page: growth chart with the flag moment, why it was flagged, quality, signals, trust |
| `Xray.dc.html` | X-ray page: architecture map, files and labelled connections, parser-verified versus AI interpretation, rejected claims, the agent's tool trace. The subject is this repository. Updated 25 Nov |
| `Scoreboard.dc.html` | Scoreboard: live alerts classed early, ambiguous or late, a design for zero hits, replays shown apart as not evidence, and the Trending repos the radar missed. Updated 25 Nov |

**What is real:** repository names, star counts, growth curves, Trending and
Hacker News data, and the Trending counts to 25 Nov on the scoreboard. **What
is a placeholder:** quality scores, fit scores, AI-written text, live alerts,
the tool trace and the rejected claims, shown in square brackets or marked as
examples, because those stages do not exist yet. Replayed flag times are what
the planned rule produced afterwards on the real snapshots. Line numbers on
the X-ray screen are illustrative.

The files are sources for a design canvas and do not render on their own in a
browser. `canvas.json` holds their layout on the canvas.

Decision (15 Nov 2026): Radar A. For the freeze it shows two lanes; the third
(Just discussed) needs Hacker News, which comes later.
