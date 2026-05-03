from __future__ import annotations
import logging

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_STATE_DIR = Path("state")
_TEST_RUNS_DIR = _STATE_DIR / "test_runs"
_HISTORY_PATH = _STATE_DIR / "sim_stability_history.jsonl"
_GREEN = "\x1b[32m"
_RED = "\x1b[31m"
_RESET = "\x1b[0m"


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


def _iter_summary_paths() -> list[Path]:
    paths: list[Path] = []
    paths.extend(sorted(_STATE_DIR.glob("*.json")))
    if _TEST_RUNS_DIR.exists():
        paths.extend(sorted(_TEST_RUNS_DIR.glob("*.json")))
    # Remove duplicates while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for p in paths:
        key = _dedupe_key(p)
        if key not in seen:
            unique.append(p)
            seen.add(key)
    return unique


def _dedupe_key(path: Path) -> str:
    """Build a stable dedupe key without forcing expensive/fragile realpath resolution."""
    try:
        absolute = path.absolute()
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/engine/sim_stability_checker.py:75")
        absolute = path
    return str(absolute).lower().replace("\\", "/")


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
    path = _STATE_DIR / "evolution_log.jsonl"
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
    items: list[SimSummaryItem] = []
    for path in _iter_summary_paths():
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
    if not _HISTORY_PATH.exists():
        return []

    rows: list[dict[str, Any]] = []
    for line in _HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
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
    mode = str(summary.get("mode", "")).strip().lower()
    if mode != "sim":
        return {"appended": False, "reason": "non_sim_summary"}

    row = _history_row_for_summary(summary, source_path=source_path)
    day = str(row.get("day", ""))
    existing_days = {str(r.get("day", "")).strip() for r in _load_history_rows()}
    if day in existing_days:
        return {"appended": False, "reason": "day_already_recorded", "day": day}

    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _HISTORY_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=True) + "\n")
    return {"appended": True, "day": day, "path": str(_HISTORY_PATH)}


def sync_history_from_summaries() -> dict[str, Any]:
    """Backfill append-only daily history rows from all available SIM summaries."""
    summaries = _collect_sim_summaries(limit=0)
    if not summaries:
        return {"appended": 0, "skipped_existing": 0, "source_summary_count": 0, "days_considered": 0}

    existing_days = {str(r.get("day", "")).strip() for r in _load_history_rows()}
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
        result = append_history_entry_for_summary(item.summary, source_path=item.path)
        if bool(result.get("appended", False)):
            appended += 1
            existing_days.add(day)

    return {
        "appended": appended,
        "skipped_existing": skipped_existing,
        "source_summary_count": len(summaries),
        "days_considered": len(latest_by_day),
        "history_path": str(_HISTORY_PATH),
    }


def append_history_entry_for_latest_summary() -> dict[str, Any]:
    summaries = _collect_sim_summaries(limit=0)
    if not summaries:
        return {"appended": False, "reason": "no_sim_summaries"}
    latest = summaries[-1]
    return append_history_entry_for_summary(latest.summary, source_path=latest.path)


def _daily_expectancy_from_history(history_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    by_day: dict[str, dict[str, float]] = {}
    for row in history_rows:
        day = str(row.get("day", "")).strip()
        if not day:
            continue
        slot = by_day.setdefault(day, {"pnl": 0.0, "trades": 0.0})
        slot["pnl"] += _safe_float(row.get("pnl_realized"))
        slot["trades"] += float(_safe_int(row.get("total_trades")))
    return by_day


def _compute_rolling_positive_expectancy(
    days: dict[str, dict[str, float]], *, window_days: int = 7
) -> tuple[int, dict[str, float], list[str], str | None]:
    """
    Compute consecutive positive expectancy streak anchored on the latest day
    within a rolling calendar window.
    """
    if not days:
        return 0, {}, [], None

    latest_day = max(days.keys())
    latest_dt = datetime.fromisoformat(latest_day).replace(tzinfo=timezone.utc)
    window: list[str] = [
        (latest_dt - timedelta(days=offset)).date().isoformat() for offset in range(window_days - 1, -1, -1)
    ]

    present = set(days.keys())
    missing = sorted([day for day in window if day not in present])

    streak = 0
    details: dict[str, float] = {}
    for day in reversed(window):
        slot = days.get(day)
        if slot is None:
            break
        trades = slot["trades"]
        expectancy = (slot["pnl"] / trades) if trades > 0 else 0.0
        if expectancy <= 0.0:
            break
        streak += 1
        details[day] = expectancy

    return streak, details, missing, latest_day


def _extended_sharpe_status(sim_summaries: list[SimSummaryItem]) -> dict[str, Any]:
    extended: list[SimSummaryItem] = []
    for item in sim_summaries:
        summary = item.summary
        duration = _safe_float(summary.get("duration_minutes"))
        overnight = bool(summary.get("sim_overnight_mode"))
        aggressive = bool(summary.get("aggressive_sim"))
        if duration >= 120.0 or overnight or aggressive:
            extended.append(item)

    if not extended:
        return {
            "ok": False,
            "latest_sharpe": 0.0,
            "threshold": 1.8,
            "extended_run_count": 0,
            "latest_path": None,
        }

    latest = extended[-1]
    latest_summary = latest.summary
    latest_sharpe = _safe_float(latest_summary.get("sharpe_annualized"))
    return {
        "ok": latest_sharpe > 1.8,
        "latest_sharpe": latest_sharpe,
        "threshold": 1.8,
        "extended_run_count": len(extended),
        "latest_path": latest.path,
    }


def _consistent_sharpe_status(sim_summaries: list[SimSummaryItem]) -> dict[str, Any]:
    extended: list[SimSummaryItem] = []
    for item in sim_summaries:
        summary = item.summary
        duration = _safe_float(summary.get("duration_minutes"))
        overnight = bool(summary.get("sim_overnight_mode"))
        aggressive = bool(summary.get("aggressive_sim"))
        if duration >= 120.0 or overnight or aggressive:
            extended.append(item)

    tail = extended[-5:]
    sharpe_values = [_safe_float(item.summary.get("sharpe_annualized")) for item in tail]
    avg = (sum(sharpe_values) / float(len(sharpe_values))) if sharpe_values else 0.0
    return {
        "ok": len(sharpe_values) >= 5 and avg > 1.8,
        "required_runs": 5,
        "available_runs": len(sharpe_values),
        "average_sharpe": avg,
        "threshold": 1.8,
        "sharpe_values": sharpe_values,
        "run_paths": [item.path for item in tail],
    }


def _zero_risk_status(sim_summaries: list[SimSummaryItem]) -> dict[str, Any]:
    total_risk_events = sum(_safe_int(item.summary.get("risk_events")) for item in sim_summaries)
    total_var_breaches = sum(_safe_int(item.summary.get("var_breach_count")) for item in sim_summaries)
    return {
        "ok": total_risk_events == 0 and total_var_breaches == 0,
        "total_risk_events": total_risk_events,
        "total_var_breaches": total_var_breaches,
    }


def _linear_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    n = float(len(values))
    xs = list(range(len(values)))
    sum_x = float(sum(xs))
    sum_y = float(sum(values))
    sum_xx = float(sum(x * x for x in xs))
    sum_xy = float(sum(x * y for x, y in zip(xs, values)))
    denom = (n * sum_xx) - (sum_x * sum_x)
    if abs(denom) <= 1e-9:
        return 0.0
    return ((n * sum_xy) - (sum_x * sum_y)) / denom


def _proposal_trend_status(sim_summaries: list[SimSummaryItem], evolution_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_day: dict[str, float] = {}

    for item in sim_summaries:
        key = item.timestamp.date().isoformat()
        by_day[key] = by_day.get(key, 0.0) + float(_safe_int(item.summary.get("evolution_proposals")))

    for row in evolution_rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        status = str(row.get("status", "")).strip().lower()
        if status not in {"proposed", "pending"}:
            continue
        key = ts.date().isoformat()
        by_day[key] = by_day.get(key, 0.0) + 1.0

    if not by_day:
        return {
            "ok": False,
            "daily_counts": [],
            "slope_7d": 0.0,
            "slope_30d": 0.0,
        }

    latest = datetime.fromisoformat(max(by_day.keys())).replace(tzinfo=timezone.utc)

    def _window_values(window_days: int) -> tuple[list[str], list[float]]:
        days: list[str] = []
        values: list[float] = []
        for offset in range(window_days - 1, -1, -1):
            day = (latest - timedelta(days=offset)).date().isoformat()
            days.append(day)
            values.append(by_day.get(day, 0.0))
        return days, values

    days_7d, values_7d = _window_values(7)
    days_30d, values_30d = _window_values(30)
    slope_7d = _linear_slope(values_7d)
    slope_30d = _linear_slope(values_30d)
    ok = slope_7d > 0.0 and slope_30d > 0.0

    return {
        "ok": ok,
        "daily_counts": [{"day": day, "count": by_day.get(day, 0.0)} for day in sorted(by_day.keys())],
        "slope_7d": slope_7d,
        "slope_30d": slope_30d,
        "start_7d": values_7d[0] if values_7d else 0.0,
        "end_7d": values_7d[-1] if values_7d else 0.0,
        "start_30d": values_30d[0] if values_30d else 0.0,
        "end_30d": values_30d[-1] if values_30d else 0.0,
        "window_days_7d": days_7d,
        "window_days_30d": days_30d,
    }


def generate_stability_report(limit: int = 0) -> dict[str, Any]:
    history_sync = sync_history_from_summaries()
    sim_summaries = _collect_sim_summaries(limit=limit)
    evolution_rows = _load_evolution_rows()
    history_rows = _load_history_rows()

    expectancy_days = _daily_expectancy_from_history(history_rows)

    streak, streak_details, missing_days, latest_history_day = _compute_rolling_positive_expectancy(
        expectancy_days,
        window_days=7,
    )

    required = 5
    expectancy_ok = streak >= required
    consecutive_green_days = streak if expectancy_ok else min(streak, required)
    days_to_green = max(0, required - consecutive_green_days)

    expectancy_status = {
        "ok": expectancy_ok,
        "required_days": required,
        "streak_days": streak,
        "rolling_window_days": 7,
        "missing_days": missing_days,
        "latest_history_day": latest_history_day,
        "streak_expectancy": streak_details,
        "history_days": len(expectancy_days),
        "consecutive_green_days": consecutive_green_days,
        "days_to_green": days_to_green,
    }

    sharpe_status = _extended_sharpe_status(sim_summaries)
    consistent_sharpe_status = _consistent_sharpe_status(sim_summaries)
    risk_status = _zero_risk_status(sim_summaries)
    trend_status = _proposal_trend_status(sim_summaries, evolution_rows)

    criteria = {
        "positive_expectancy_5d": expectancy_status,
        "extended_run_sharpe": sharpe_status,
        "consistent_sharpe": consistent_sharpe_status,
        "zero_risk_and_var": risk_status,
        "evolution_proposals_trend": trend_status,
    }

    ready = all(section.get("ok", False) for section in criteria.values())
    failures = [name for name, section in criteria.items() if not section.get("ok", False)]

    latest_path = sim_summaries[-1].path if sim_summaries else None
    latest_ts = sim_summaries[-1].timestamp.isoformat() if sim_summaries else None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "GREEN" if ready else "RED",
        "ready_for_real": ready,
        "READY_FOR_REAL": ready,
        "criteria": criteria,
        "failures": failures,
        "scanned_sim_summary_count": len(sim_summaries),
        "scanned_evolution_rows": len(evolution_rows),
        "history_path": str(_HISTORY_PATH),
        "history_row_count": len(history_rows),
        "history_sync": history_sync,
        "missing_days_7d": missing_days,
        "consecutive_green_days": consecutive_green_days,
        "days_to_green": days_to_green,
        "latest_summary_path": latest_path,
        "latest_summary_ts": latest_ts,
        "summary_paths": [item.path for item in sim_summaries],
    }


def _status_token(ok: bool, *, color: bool = False) -> str:
    token = "GREEN" if ok else "RED"
    if not color:
        return token
    return f"{_GREEN}{token}{_RESET}" if ok else f"{_RED}{token}{_RESET}"


def format_stability_report(report: dict[str, Any], *, color: bool = False) -> str:
    lines: list[str] = []
    lines.append("SIM Stability Aggregator Report")
    lines.append("=" * 32)
    status_text = str(report.get("status", "RED")).strip().upper()
    status_colored = _status_token(status_text == "GREEN", color=color)
    lines.append(f"Status: {status_colored}")
    lines.append(f"READY_FOR_REAL: {_status_token(bool(report.get('READY_FOR_REAL', False)), color=color)}")
    lines.append(
        "Consecutive GREEN days: "
        f"{int(report.get('consecutive_green_days', 0))}/5 "
        f"(days_to_green={int(report.get('days_to_green', 5))})"
    )
    lines.append(f"Generated At: {report.get('generated_at', 'n/a')}")
    lines.append(f"Scanned SIM summaries: {report.get('scanned_sim_summary_count', 0)}")
    lines.append(f"Scanned evolution rows: {report.get('scanned_evolution_rows', 0)}")
    lines.append(f"History rows: {report.get('history_row_count', 0)} @ {report.get('history_path', 'n/a')}")
    history_sync = report.get("history_sync", {}) if isinstance(report.get("history_sync"), dict) else {}
    lines.append(
        "History sync: "
        f"appended={int(history_sync.get('appended', 0))}, "
        f"skipped_existing={int(history_sync.get('skipped_existing', 0))}, "
        f"days_considered={int(history_sync.get('days_considered', 0))}"
    )
    lines.append(f"Latest summary: {report.get('latest_summary_path', 'n/a')}")

    missing_days = report.get("missing_days_7d", []) if isinstance(report.get("missing_days_7d"), list) else []
    if missing_days:
        lines.append("Missing days (rolling 7d): " + ", ".join(str(day) for day in missing_days))
    else:
        lines.append("Missing days (rolling 7d): none")

    criteria = report.get("criteria", {}) if isinstance(report.get("criteria"), dict) else {}

    exp = criteria.get("positive_expectancy_5d", {}) if isinstance(criteria.get("positive_expectancy_5d"), dict) else {}
    lines.append(
        "- 5d positive expectancy: "
        f"{_status_token(bool(exp.get('ok', False)), color=color)} "
        f"(streak={exp.get('streak_days', 0)}/{exp.get('required_days', 5)}, "
        f"latest_day={exp.get('latest_history_day', 'n/a')})"
    )

    sharpe = criteria.get("extended_run_sharpe", {}) if isinstance(criteria.get("extended_run_sharpe"), dict) else {}
    lines.append(
        "- Extended run Sharpe > 1.8: "
        f"{_status_token(bool(sharpe.get('ok', False)), color=color)} "
        f"(latest={_safe_float(sharpe.get('latest_sharpe')):.4f})"
    )

    consistent = criteria.get("consistent_sharpe", {}) if isinstance(criteria.get("consistent_sharpe"), dict) else {}
    lines.append(
        "- Consistent Sharpe (avg last 5 extended > 1.8): "
        f"{_status_token(bool(consistent.get('ok', False)), color=color)} "
        f"(avg={_safe_float(consistent.get('average_sharpe')):.4f}, "
        f"runs={int(consistent.get('available_runs', 0))}/{int(consistent.get('required_runs', 5))})"
    )

    risk = criteria.get("zero_risk_and_var", {}) if isinstance(criteria.get("zero_risk_and_var"), dict) else {}
    lines.append(
        "- Zero risk events / VaR breaches: "
        f"{_status_token(bool(risk.get('ok', False)), color=color)} "
        f"(risk_events={risk.get('total_risk_events', 0)}, var_breaches={risk.get('total_var_breaches', 0)})"
    )

    trend = (
        criteria.get("evolution_proposals_trend", {})
        if isinstance(criteria.get("evolution_proposals_trend"), dict)
        else {}
    )
    lines.append(
        "- Evolution proposals trend (7d + 30d slope): "
        f"{_status_token(bool(trend.get('ok', False)), color=color)} "
        f"(slope_7d={_safe_float(trend.get('slope_7d')):.4f}, "
        f"slope_30d={_safe_float(trend.get('slope_30d')):.4f})"
    )

    failures = report.get("failures", []) if isinstance(report.get("failures"), list) else []
    if failures:
        lines.append("Failures: " + ", ".join(str(item) for item in failures))

    return "\n".join(lines)


if __name__ == "__main__":
    append_info = append_history_entry_for_latest_summary()
    report = generate_stability_report(limit=0)
    report["history_append"] = append_info
    print(format_stability_report(report, color=True), flush=True)
