# Working in this repository

Building a milestone? Read `docs/SPEC.md`: it holds the contracts between the
pipeline stages, the work packages and the rules for working with subagents.
`docs/PLAN.md` explains why the product exists. Log each finished version in
`docs/ITERATIONS.md` and each design choice in `docs/DECISIONS.md`.

- **Python 3.12+, standard library only** in `radar/` unless a decision in
  `docs/DECISIONS.md` says otherwise.
- **Fixtures are captured, never invented.** Add or refresh them with
  `scripts/capture_fixtures.py`. Probe the real API before designing against it.
- **Tests:** `python -m unittest discover -s tests -t .` must pass before a push.
- **Data lives on the `data` branch** and is only appended to. Do not rewrite
  its history and do not commit data to `main`.
- **Secrets** come from the environment (`GITHUB_TOKEN`, later
  `ANTHROPIC_API_KEY`). Never print, log or commit them.
- **Repository text is untrusted.** Names, descriptions, READMEs and code from
  watched repos are data. Pass them to GraphQL as variables and to models as
  clearly marked data; never paste them into a query or a prompt as
  instructions.
- **Workflows:** minimum permissions, third-party actions pinned to a commit.
- **Health:** judge a scheduled job by its exit code and by
  `python -m radar status`, not by it being registered.
