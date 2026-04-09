from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_STATE_DIR = Path("state")
_TEST_RUNS_DIR = _STATE_DIR / "test_runs"


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
    paths.extend(sorted(_STATE_DIR.glob("last_run_summary*.json")))
    paths.extend(sorted(_TEST_RUNS_DIR.glob("summary_sim_*.json")))
    # Remove duplicates while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in paths:
        rp = p.resolve()
        if rp not in seen:
            unique.append(p)
            seen.add(rp)
    return unique


def _load_summary(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _is_sim_summary(path: Path, summary: dict[str, Any]) -> bool:
    mode = str(summary.get("mode", "")).strip().lower()
    if mode == "sim":
        return True
    return "_sim_" in path.name.lower()


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


def _collect_sim_summaries(limit: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in _iter_summary_paths():
        summary = _load_summary(path)
        if summary is None:
            continue
        if not _is_sim_summary(path, summary):
            continue
        ts = _parse_ts(summary.get("finished_at") or summary.get("started_at"))
        if ts is None:
            ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        items.append({"path": str(path), "timestamp": ts, "summary": summary})
    items.sort(key=lambda x: x["timestamp"])
    if limit > 0:
        items = items[-limit:]
    return items


def _aggregate_daily_expectancy(sim_summaries: list[dict[str, Any]], evolution_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    buckets: dict[str, dict[str, float]] = {}

    for item in sim_summaries:
        summary = item["summary"]
        ts_raw = item.get("timestamp")
        ts = ts_raw if isinstance(ts_raw, datetime) else None
        if ts is None:
            continue
        key = ts.date().isoformat()
        slot = buckets.setdefault(key, {"pnl": 0.0, "trades": 0.0})
        slot["pnl"] += _safe_float(summary.get("pnl_realized"))
        slot["trades"] += float(_safe_int(summary.get("total_trades")))

    for row in evolution_rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        key = ts.date().isoformat()
        meta_raw = row.get("meta_review")
        meta = meta_raw if isinstance(meta_raw, dict) else {}
        slot = buckets.setdefault(key, {"pnl": 0.0, "trades": 0.0})
        slot["pnl"] += _safe_float(meta.get("net_pnl"))
        slot["trades"] += float(_safe_int(meta.get("trades")))

    return buckets


def _compute_positive_expectancy_streak(days: dict[str, dict[str, float]]) -> tuple[int, dict[str, float]]:
    if not days:
        return 0, {}

    ordered = sorted(days.keys(), reverse=True)
    streak = 0
    current_date: datetime | None = None
    details: dict[str, float] = {}

    for day in ordered:
        day_dt = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        trades = days[day]["trades"]
        expectancy = (days[day]["pnl"] / trades) if trades > 0 else 0.0

        if current_date is None:
            if expectancy <= 0:
                break
            streak = 1
            details[day] = expectancy
            current_date = day_dt
            continue

        if (current_date - day_dt).days != 1 or expectancy <= 0:
            break

        streak += 1
        details[day] = expectancy
        current_date = day_dt

    return streak, details


def _extended_sharpe_status(sim_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    extended: list[dict[str, Any]] = []
    for item in sim_summaries:
        summary = item["summary"]
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
    latest_summary = latest["summary"]
    latest_sharpe = _safe_float(latest_summary.get("sharpe_annualized"))
    return {
        "ok": latest_sharpe > 1.8,
        "latest_sharpe": latest_sharpe,
        "threshold": 1.8,
        "extended_run_count": len(extended),
        "latest_path": latest["path"],
    }


def _zero_risk_status(sim_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    total_risk_events = sum(_safe_int(item["summary"].get("risk_events")) for item in sim_summaries)
    total_var_breaches = sum(_safe_int(item["summary"].get("var_breach_count")) for item in sim_summaries)
    return {
        "ok": total_risk_events == 0 and total_var_breaches == 0,
        "total_risk_events": total_risk_events,
        "total_var_breaches": total_var_breaches,
    }


def _proposal_trend_status(sim_summaries: list[dict[str, Any]], evolution_rows: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)
    by_day: dict[str, float] = {}

    for item in sim_summaries:
        ts_raw = item.get("timestamp")
        ts = ts_raw if isinstance(ts_raw, datetime) else None
        if ts is None:
            continue
        if ts < since:
            continue
        key = ts.date().isoformat()
        by_day[key] = by_day.get(key, 0.0) + float(_safe_int(item["summary"].get("evolution_proposals")))

    for row in evolution_rows:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None or ts < since:
            continue
        status = str(row.get("status", "")).strip().lower()
        if status not in {"proposed", "pending"}:
            continue
        key = ts.date().isoformat()
        by_day[key] = by_day.get(key, 0.0) + 1.0

    days = sorted(by_day.keys())
    values = [by_day[d] for d in days]

    slope = 0.0
    if len(values) >= 2:
        n = float(len(values))
        xs = list(range(len(values)))
        sum_x = float(sum(xs))
        sum_y = float(sum(values))
        sum_xx = float(sum(x * x for x in xs))
        sum_xy = float(sum(x * y for x, y in zip(xs, values)))
        denom = (n * sum_xx) - (sum_x * sum_x)
        if abs(denom) > 1e-9:
            slope = ((n * sum_xy) - (sum_x * sum_y)) / denom

    ok = len(values) >= 2 and slope > 0.0 and values[-1] >= values[0]
    return {
        "ok": ok,
        "window_days": 7,
        "daily_counts": [{"day": d, "count": by_day[d]} for d in days],
        "slope": slope,
        "start_count": values[0] if values else 0.0,
        "end_count": values[-1] if values else 0.0,
    }


def generate_stability_report(limit: int = 30) -> dict[str, Any]:
    sim_summaries = _collect_sim_summaries(limit=limit)
    evolution_rows = _load_evolution_rows()

    daily = _aggregate_daily_expectancy(sim_summaries=sim_summaries, evolution_rows=evolution_rows)
    streak, streak_details = _compute_positive_expectancy_streak(daily)
    expectancy_status = {
        "ok": streak >= 5,
        "required_days": 5,
        "streak_days": streak,
        "streak_expectancy": streak_details,
    }

    sharpe_status = _extended_sharpe_status(sim_summaries)
    risk_status = _zero_risk_status(sim_summaries)
    trend_status = _proposal_trend_status(sim_summaries, evolution_rows)

    criteria = {
        "positive_expectancy_5d": expectancy_status,
        "extended_run_sharpe": sharpe_status,
        "zero_risk_and_var": risk_status,
        "evolution_proposals_trend": trend_status,
    }

    ready = all(section.get("ok", False) for section in criteria.values())
    failures = [name for name, section in criteria.items() if not section.get("ok", False)]

    latest_path = sim_summaries[-1]["path"] if sim_summaries else None
    latest_ts = sim_summaries[-1]["timestamp"].isoformat() if sim_summaries else None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "GREEN" if ready else "RED",
        "ready_for_real": ready,
        "READY_FOR_REAL": ready,
        "criteria": criteria,
        "failures": failures,
        "scanned_sim_summary_count": len(sim_summaries),
        "scanned_evolution_rows": len(evolution_rows),
        "latest_summary_path": latest_path,
        "latest_summary_ts": latest_ts,
        "summary_paths": [item["path"] for item in sim_summaries],
    }


def format_stability_report(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("SIM Stability Aggregator Report")
    lines.append("=" * 32)
    lines.append(f"Status: {report.get('status', 'RED')}")
    lines.append(f"READY_FOR_REAL: {bool(report.get('READY_FOR_REAL', False))}")
    lines.append(f"Generated At: {report.get('generated_at', 'n/a')}")
    lines.append(f"Scanned SIM summaries: {report.get('scanned_sim_summary_count', 0)}")
    lines.append(f"Scanned evolution rows: {report.get('scanned_evolution_rows', 0)}")
    lines.append(f"Latest summary: {report.get('latest_summary_path', 'n/a')}")

    criteria = report.get("criteria", {}) if isinstance(report.get("criteria"), dict) else {}

    exp = criteria.get("positive_expectancy_5d", {}) if isinstance(criteria.get("positive_expectancy_5d"), dict) else {}
    lines.append(
        "- 5d positive expectancy: "
        f"{'PASS' if exp.get('ok') else 'FAIL'} "
        f"(streak={exp.get('streak_days', 0)}/{exp.get('required_days', 5)})"
    )

    sharpe = criteria.get("extended_run_sharpe", {}) if isinstance(criteria.get("extended_run_sharpe"), dict) else {}
    lines.append(
        "- Extended run Sharpe > 1.8: "
        f"{'PASS' if sharpe.get('ok') else 'FAIL'} "
        f"(latest={_safe_float(sharpe.get('latest_sharpe')):.4f})"
    )

    risk = criteria.get("zero_risk_and_var", {}) if isinstance(criteria.get("zero_risk_and_var"), dict) else {}
    lines.append(
        "- Zero risk events / VaR breaches: "
        f"{'PASS' if risk.get('ok') else 'FAIL'} "
        f"(risk_events={risk.get('total_risk_events', 0)}, var_breaches={risk.get('total_var_breaches', 0)})"
    )

    trend = criteria.get("evolution_proposals_trend", {}) if isinstance(criteria.get("evolution_proposals_trend"), dict) else {}
    lines.append(
        "- Evolution proposals trend upward: "
        f"{'PASS' if trend.get('ok') else 'FAIL'} "
        f"(slope={_safe_float(trend.get('slope')):.4f}, "
        f"start={_safe_float(trend.get('start_count')):.1f}, end={_safe_float(trend.get('end_count')):.1f})"
    )

    failures = report.get("failures", []) if isinstance(report.get("failures"), list) else []
    if failures:
        lines.append("Failures: " + ", ".join(str(item) for item in failures))

    return "\n".join(lines)
