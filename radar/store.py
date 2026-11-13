"""The data store: plain files on the `data` branch.

Layout (everything UTF-8, one JSON object per line):

    repos.jsonl                         append-only registry, one line per repo ever seen
    gone.jsonl                          append-only list of repos that disappeared
    snapshots/YYYY/MM/DD/HHMMSSZ.jsonl.gz   star counts for every watched repo, one file per run
    trending/YYYY-MM.jsonl              what github.com/trending showed, appended each run
    runs.jsonl                          one summary line per collector run

Files are only ever appended or created, never rewritten, so every run adds
a small, reviewable change to the branch.
"""

from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

REGISTRY = "repos.jsonl"
GONE = "gone.jsonl"
RUNS = "runs.jsonl"


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    # A line that is not valid JSON (a write cut short by a crash) is skipped,
    # so one damaged line cannot stop every later run. A damaged gzip file raises.
    if not path.exists():
        return
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    # If an earlier write was cut short, start on a fresh line so new rows stay readable.
    needs_newline = False
    if path.exists() and path.stat().st_size:
        with open(path, "rb") as existing:
            existing.seek(-1, os.SEEK_END)
            needs_newline = existing.read(1) != b"\n"
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        if needs_newline:
            handle.write("\n")
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def load_registry(data_dir: Path) -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in read_jsonl(data_dir / REGISTRY) if "id" in row}


def load_gone(data_dir: Path) -> set[str]:
    return {row["id"] for row in read_jsonl(data_dir / GONE) if "id" in row}


def snapshot_path(data_dir: Path, moment: datetime) -> Path:
    utc = moment.astimezone(timezone.utc)
    return data_dir / "snapshots" / utc.strftime("%Y/%m/%d") / utc.strftime("%H%M%SZ.jsonl.gz")


def write_snapshot(data_dir: Path, moment: datetime, rows: Iterable[dict[str, Any]]) -> Path:
    path = snapshot_path(data_dir, moment)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Written under a temporary name and renamed, so a crash never leaves a
    # half-written snapshot. mtime=0 keeps the bytes identical for identical content.
    partial = path.with_name(path.name + ".partial")
    with open(partial, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as packed:
        for row in rows:
            line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
            packed.write(line.encode("utf-8"))
    os.replace(partial, path)
    return path


def list_snapshots(data_dir: Path) -> list[Path]:
    return sorted((data_dir / "snapshots").glob("*/*/*/*.jsonl.gz"))


def snapshot_time(path: Path) -> datetime:
    year, month, day = path.parts[-4:-1]
    clock = path.name.split("Z")[0]
    return datetime.strptime(f"{year}{month}{day}{clock}", "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc
    )


def trending_path(data_dir: Path, moment: datetime) -> Path:
    return data_dir / "trending" / moment.astimezone(timezone.utc).strftime("%Y-%m.jsonl")
