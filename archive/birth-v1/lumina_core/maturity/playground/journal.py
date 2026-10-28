"""Append-only Playground heartbeat journal. Playground wipe does not delete it."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JOURNAL_DIR = Path("reports") / "playground_cycle_journal"
HEARTBEAT_NAME = "heartbeats.jsonl"
HEARTBEAT_SCHEMA = "playground_heartbeat_v1"


def journal_dir(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / JOURNAL_DIR


def heartbeat_path(workspace_root: Path | str) -> Path:
    return journal_dir(workspace_root) / HEARTBEAT_NAME


def append_heartbeat(workspace_root: Path | str, row: dict[str, Any]) -> None:
    path = heartbeat_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(row)
    payload["schema"] = HEARTBEAT_SCHEMA
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
    line = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


EXPERIMENT_NAME = "EXPERIMENT.md"


def experiment_path(workspace_root: Path | str) -> Path:
    return journal_dir(workspace_root) / EXPERIMENT_NAME


def append_experiment_entry(
    workspace_root: Path | str,
    *,
    title: str,
    lines: list[str],
) -> None:
    """Append one dated section. Never rewrites earlier experiments."""
    path = experiment_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_text(_empty_book(), encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = "\n".join(str(line) for line in lines).rstrip() + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## {stamp} — {title}\n\n{body}\n")


def _empty_book() -> str:
    return (
        "# Playground cycle journal\n\n"
        "Append-only. A Playground wipe deletes tape, progress, occupancy, and the crawl cursor. "
        "It does not delete this directory.\n\n"
        "Do not re-test: the empty session_watch clock, JSON-as-fill, grading Birth tape as "
        "Playground, lowering a floor, scoring the 25 Sep halt as a pass, or treating a 2s poll "
        "as a stall window.\n"
    )


def load_heartbeats(workspace_root: Path | str) -> list[dict[str, Any]]:
    path = heartbeat_path(workspace_root)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows
