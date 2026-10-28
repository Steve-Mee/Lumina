"""Append-only Awakening cycle journal. Awakening wipe does not delete it."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JOURNAL_DIR = Path("reports") / "awakening_cycle_journal"
JOURNAL_NAME = "cycles.jsonl"


def journal_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / JOURNAL_DIR / JOURNAL_NAME


def new_run_id() -> str:
    """One id per living-clock invocation. Journal rows keep it across a wipe."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def append_cycle(workspace_root: Path | str, row: dict[str, Any]) -> None:
    path = journal_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=True, sort_keys=True, default=str) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def load_cycles(workspace_root: Path | str) -> list[dict[str, Any]]:
    path = journal_path(workspace_root)
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


def best_discarded_child(rows: list[dict[str, Any]], *, run_id: str) -> dict[str, Any] | None:
    """Highest lift among this run's rejected shots. Ties break toward lower DD."""
    if not str(run_id):
        return None
    best: dict[str, Any] | None = None
    best_key: tuple[float, float] | None = None
    for row in rows:
        if row.get("phase_exit") is True:
            continue
        if str(row.get("run_id") or "") != str(run_id):
            continue
        if row.get("kept") is not False or row.get("eval_only") is True:
            continue
        lift = _f(row.get("lift"))
        if lift is None:
            continue
        dd = _f(row.get("dd_pct"))
        key = (float(lift), -(float(dd) if dd is not None else 1_000_000_000.0))
        if best_key is None or key > best_key:
            best = row
            best_key = key
    return best


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
