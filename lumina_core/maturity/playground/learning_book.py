"""Lumina's learning book. Append-only. Not the experiment book.

ADR-0056. A Playground wipe of state/ does not delete reports/playground_learning_book.
The operator writes the budget and the draw seed before any program of that period.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BOOK_DIR = Path("reports") / "playground_learning_book"
HEADER_NAME = "header.json"
NAMES_NAME = "names.jsonl"
OUTCOMES_NAME = "outcomes.jsonl"

FORWARD_MIN = 30


class LearningBookError(ValueError):
    """The book refused a write."""


def book_dir(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / BOOK_DIR


def read_header(workspace_root: Path | str) -> dict[str, Any]:
    path = book_dir(workspace_root) / HEADER_NAME
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LearningBookError("header_unreadable") from exc
    if not isinstance(raw, dict):
        raise LearningBookError("header_unreadable")
    return raw


def write_operator_period(
    workspace_root: Path | str,
    *,
    period_id: str,
    budget: int,
    seed: int,
    cutoff_ns: int,
    tape_count: int,
    tail_start_ns: int,
    tail_end_ns: int,
    now: datetime,
) -> dict[str, Any]:
    """Operator fact. Refused once any program of this period exists."""
    period = _period(period_id)
    if _programs_for(workspace_root, period):
        raise LearningBookError("budget_after_program")
    amount = _budget(budget)
    draw_seed = _seed(seed)
    if int(tail_end_ns) <= int(tail_start_ns) or int(tail_end_ns) > int(cutoff_ns):
        raise LearningBookError("tail_bounds")
    if now.tzinfo is None:
        raise LearningBookError("naive_timestamp")
    header = read_header(workspace_root)
    periods = dict(header.get("periods") or {})
    if period in periods:
        raise LearningBookError("period_already_written")
    periods[period] = {
        "budget": amount,
        "seed": draw_seed,
        "cutoff_ns": int(cutoff_ns),
        "tape_count": int(tape_count),
        "tail_start_ns": int(tail_start_ns),
        "tail_end_ns": int(tail_end_ns),
        "written_at": now.astimezone(timezone.utc).isoformat(),
        "writer": "operator",
    }
    header["periods"] = periods
    _write_header(workspace_root, header)
    return periods[period]


def append_name(workspace_root: Path | str, row: dict[str, Any]) -> None:
    append_names(workspace_root, [row])


def append_names(workspace_root: Path | str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path = book_dir(workspace_root) / NAMES_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()


def append_outcome(workspace_root: Path | str, row: dict[str, Any]) -> None:
    _append(workspace_root, OUTCOMES_NAME, row)


def load_names(workspace_root: Path | str) -> tuple[dict[str, Any], ...]:
    return _load(workspace_root, NAMES_NAME)


def load_outcomes(workspace_root: Path | str) -> tuple[dict[str, Any], ...]:
    return _load(workspace_root, OUTCOMES_NAME)


def record_archive_fact(
    workspace_root: Path | str,
    *,
    tape_count: int,
    minute_count: int,
    holdout_start_ns: int,
    tail_end_ns: int,
    symbol: str,
) -> dict[str, Any]:
    """Counted tape and the first cutoff. This does not open a search period."""
    if int(tape_count) < 0 or int(minute_count) < 0:
        raise LearningBookError("tape_count_invalid")
    if int(tail_end_ns) < int(holdout_start_ns):
        raise LearningBookError("tail_bounds")
    header = read_header(workspace_root)
    header["tape_count"] = int(tape_count)
    header["minute_count"] = int(minute_count)
    header["holdout_start_ns"] = int(holdout_start_ns)
    header["tail_end_ns"] = int(tail_end_ns)
    header["symbol"] = str(symbol)
    header["cutoff_rule"] = "first_holdout_bar"
    _write_header(workspace_root, header)
    return header


def mark_period(workspace_root: Path | str, period_id: str, **fields: Any) -> dict[str, Any]:
    """Update a sealed period. The tail bounds and the seed do not move."""
    header = read_header(workspace_root)
    periods = dict(header.get("periods") or {})
    key = _period(period_id)
    current = periods.get(key)
    if not isinstance(current, dict):
        raise LearningBookError("period_missing")
    for frozen in ("seed", "cutoff_ns", "tail_start_ns", "tail_end_ns", "budget"):
        if frozen in fields and fields[frozen] != current.get(frozen):
            raise LearningBookError("tail_already_sealed")
    current.update({key: value for key, value in fields.items() if key not in {"seed", "cutoff_ns", "tail_start_ns", "tail_end_ns", "budget"}})
    periods[key] = current
    header["periods"] = periods
    _write_header(workspace_root, header)
    return current


def period_budget(workspace_root: Path | str, period_id: str) -> dict[str, Any] | None:
    periods = read_header(workspace_root).get("periods") or {}
    row = periods.get(_period(period_id))
    return dict(row) if isinstance(row, dict) else None


def _programs_for(workspace_root: Path | str, period_id: str) -> list[dict[str, Any]]:
    return [row for row in load_names(workspace_root) if str(row.get("budget_id") or "") == period_id]


def _write_header(workspace_root: Path | str, header: dict[str, Any]) -> None:
    path = book_dir(workspace_root) / HEADER_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(header, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append(workspace_root: Path | str, name: str, row: dict[str, Any]) -> None:
    path = book_dir(workspace_root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()


def _load(workspace_root: Path | str, name: str) -> tuple[dict[str, Any], ...]:
    path = book_dir(workspace_root) / name
    if not path.is_file():
        return ()
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if isinstance(raw, dict):
            out.append(raw)
    return tuple(out)


def _period(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise LearningBookError("period_missing")
    return text


def _budget(value: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise LearningBookError("budget_invalid") from exc
    if out < 1:
        raise LearningBookError("budget_invalid")
    return out


def _seed(value: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise LearningBookError("seed_invalid") from exc
