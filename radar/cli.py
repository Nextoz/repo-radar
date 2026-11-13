"""Command line: `python -m radar <command>`."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import collect as collector
from . import store

MAX_AGE_HOURS = 7  # the schedule is every 3 hours; two missed runs is unhealthy


def cmd_collect(args: argparse.Namespace) -> int:
    report = collector.collect(Path(args.data))
    return 0 if report.ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Health check: judge the pipeline by the age of its newest data file."""
    data_dir = Path(args.data)
    snapshots = store.list_snapshots(data_dir)
    if not snapshots:
        print("status: no snapshots yet")
        return 1
    newest = snapshots[-1]
    age_hours = (datetime.now(timezone.utc) - store.snapshot_time(newest)).total_seconds() / 3600
    try:
        rows = sum(1 for _ in store.read_jsonl(newest))
    except (OSError, EOFError) as error:
        print(f"status: UNREADABLE newest snapshot ({type(error).__name__})")
        return 1
    runs = list(store.read_jsonl(data_dir / store.RUNS))
    failed = sum(1 for run in runs if not run.get("ok"))
    print(f"snapshots: {len(snapshots)}  newest: {newest.relative_to(data_dir).as_posix()}")
    print(f"newest age: {age_hours:.1f} h  rows: {rows}")
    print(f"watched repos: {len(store.load_registry(data_dir))}  gone: {len(store.load_gone(data_dir))}")
    print(f"runs: {len(runs)}  failed: {failed}")
    last_run_ok = bool(runs) and bool(runs[-1].get("ok"))
    fresh = 0 <= age_hours <= args.max_age_hours  # a snapshot from the future is a clock fault
    if not fresh:
        print(f"status: STALE (age {age_hours:.1f} h, limit {args.max_age_hours} h)")
    elif rows == 0:
        print("status: EMPTY newest snapshot")
    elif not last_run_ok:
        print("status: LAST RUN FAILED (see runs.jsonl)")
    else:
        print("status: healthy")
        return 0
    return 1


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy codepage; repo descriptions are UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="radar", description="Repo Radar pipeline")
    commands = parser.add_subparsers(dest="command", required=True)

    collect = commands.add_parser("collect", help="discover repos and snapshot star counts")
    collect.add_argument("--data", required=True, help="checkout of the data branch")
    collect.set_defaults(run=cmd_collect)

    status = commands.add_parser("status", help="check that data is fresh")
    status.add_argument("--data", required=True)
    status.add_argument("--max-age-hours", type=float, default=MAX_AGE_HOURS)
    status.set_defaults(run=cmd_status)

    args = parser.parse_args(argv)
    return args.run(args)
