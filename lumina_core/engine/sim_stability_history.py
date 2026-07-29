"""SIM stability history I/O — collect / sync / append for ``sim_stability_checker``."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_STATE_DIR_DEFAULT = Path("state")
_TEST_RUNS_DIR_DEFAULT = _STATE_DIR_DEFAULT / "test_runs"
_HISTORY_PATH_DEFAULT = _STATE_DIR_DEFAULT / "sim_stability_history.jsonl"


def _facade() -> Any:
    """Late-bind façade so monkeypatches on ``sim_stability_checker`` apply."""
    from lumina_core.engine import sim_stability_checker as ssc

    return ssc


@dataclass(frozen=True)
class SimSummaryItem:
    path: str
    timestamp: datetime
    summary: dict[str, Any]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _dedupe_key(path: Path) -> str:
    """Build a stable dedupe key without forcing expensive/fragile realpath resolution."""
    try:
        absolute = path.absolute()
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/sim_stability_checker.py:75")
        absolute = path
    return str(absolute).lower().replace("\\", "/")


def _iter_summary_paths() -> list[Path]:
    facade = _facade()
    state_dir: Path = facade._STATE_DIR
    test_runs_dir: Path = facade._TEST_RUNS_DIR
    paths: list[Path] = []
    paths.extend(sorted(state_dir.glob("*.json")))
    if test_runs_dir.exists():
        paths.extend(sorted(test_runs_dir.glob("*.json")))
    # Remove duplicates while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        key = facade._dedupe_key(p)
        if key not in seen:
            unique.append(p)
            seen.add(key)
    return unique


def _load_summary(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/sim_stability_checker.py:83")
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _is_sim_summary(path: Path, summary: dict[str, Any]) -> bool:
    mode = str(summary.get("mode", "")).strip().lower()
    if mode == "sim":
        return True
    name = path.name.lower()
    return "_sim_" in name or name.startswith("summary_sim_")


def _load_evolution_rows() -> list[dict[str, Any]]:
    facade = _facade()
    path = facade._STATE_DIR / "evolution_log.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    rows.sort(key=lambda r: _parse_ts(r.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
    return rows


def _collect_sim_summaries(limit: int = 0) -> list[SimSummaryItem]:
    facade = _facade()
    items: list[SimSummaryItem] = []
    for path in facade._iter_summary_paths():
        summary = _load_summary(path)
        if summary is None:
            continue
        if not _is_sim_summary(path, summary):
            continue
        ts = _parse_ts(summary.get("finished_at") or summary.get("started_at"))
        if ts is None:
            ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        items.append(SimSummaryItem(path=str(path), timestamp=ts, summary=summary))
    items.sort(key=lambda x: x.timestamp)
    if limit > 0:
        items = items[-limit:]
    return items


def _load_history_rows() -> list[dict[str, Any]]:
    facade = _facade()
    history_path: Path = facade._HISTORY_PATH
    if not history_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)

    rows.sort(key=lambda r: _parse_ts(r.get("recorded_at")) or datetime.min.replace(tzinfo=timezone.utc))
    return rows


def _history_row_for_summary(summary: dict[str, Any], *, source_path: str | None = None) -> dict[str, Any]:
    ts = _parse_ts(summary.get("finished_at") or summary.get("started_at")) or datetime.now(timezone.utc)
    trades = _safe_int(summary.get("total_trades"))
    pnl = _safe_float(summary.get("pnl_realized"))
    expectancy = (pnl / float(trades)) if trades > 0 else 0.0
    return {
        "day": ts.date().isoformat(),
        "recorded_at": ts.isoformat(),
        "source_summary_path": source_path,
        "mode": str(summary.get("mode", "")).strip().lower(),
        "broker_mode": str(summary.get("broker_mode", "")).strip().lower(),
        "duration_minutes": _safe_float(summary.get("duration_minutes")),
        "aggressive_sim": bool(summary.get("aggressive_sim")),
        "sim_overnight_mode": bool(summary.get("sim_overnight_mode")),
        "pnl_realized": pnl,
        "total_trades": trades,
        "expectancy": expectancy,
        "sharpe_annualized": _safe_float(summary.get("sharpe_annualized")),
        "risk_events": _safe_int(summary.get("risk_events")),
        "var_breach_count": _safe_int(summary.get("var_breach_count")),
        "evolution_proposals": _safe_int(summary.get("evolution_proposals")),
    }


def append_history_entry_for_summary(summary: dict[str, Any], *, source_path: str | None = None) -> dict[str, Any]:
    facade = _facade()
    mode = str(summary.get("mode", "")).strip().lower()
    if mode != "sim":
        return {"appended": False, "reason": "non_sim_summary"}

    row = _history_row_for_summary(summary, source_path=source_path)
    day = str(row.get("day", ""))
    existing_days = {str(r.get("day", "")).strip() for r in facade._load_history_rows()}
    if day in existing_days:
        return {"appended": False, "reason": "day_already_recorded", "day": day}

    history_path: Path = facade._HISTORY_PATH
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")
    return {"appended": True, "day": day, "path": str(history_path)}


def sync_history_from_summaries() -> dict[str, Any]:
    """Backfill append-only daily history rows from all available SIM summaries."""
    facade = _facade()
    summaries = facade._collect_sim_summaries(limit=0)
    if not summaries:
        return {"appended": 0, "skipped_existing": 0, "source_summary_count": 0, "days_considered": 0}

    existing_days = {str(r.get("day", "")).strip() for r in facade._load_history_rows()}
    # Keep the latest summary per day as that day's canonical snapshot.
    latest_by_day: dict[str, SimSummaryItem] = {}
    for item in summaries:
        day = item.timestamp.date().isoformat()
        prev = latest_by_day.get(day)
        if prev is None or item.timestamp > prev.timestamp:
            latest_by_day[day] = item

    appended = 0
    skipped_existing = 0
    for day in sorted(latest_by_day.keys()):
        if day in existing_days:
            skipped_existing += 1
            continue
        item = latest_by_day[day]
        result = facade.append_history_entry_for_summary(item.summary, source_path=item.path)
        if bool(result.get("appended", False)):
            appended += 1
            existing_days.add(day)

    return {
        "appended": appended,
        "skipped_existing": skipped_existing,
        "source_summary_count": len(summaries),
        "days_considered": len(latest_by_day),
        "history_path": str(facade._HISTORY_PATH),
    }


def append_history_entry_for_latest_summary() -> dict[str, Any]:
    facade = _facade()
    summaries = facade._collect_sim_summaries(limit=0)
    if not summaries:
        return {"appended": False, "reason": "no_sim_summaries"}
    latest = summaries[-1]
    return facade.append_history_entry_for_summary(latest.summary, source_path=latest.path)


__all__ = [
    "SimSummaryItem",
    "_STATE_DIR_DEFAULT",
    "_TEST_RUNS_DIR_DEFAULT",
    "_HISTORY_PATH_DEFAULT",
    "_safe_float",
    "_safe_int",
    "_parse_ts",
    "_dedupe_key",
    "_iter_summary_paths",
    "_load_summary",
    "_is_sim_summary",
    "_load_evolution_rows",
    "_collect_sim_summaries",
    "_load_history_rows",
    "_history_row_for_summary",
    "append_history_entry_for_summary",
    "sync_history_from_summaries",
    "append_history_entry_for_latest_summary",
]
