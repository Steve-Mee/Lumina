"""Build REAL operations snapshot for core telemetry."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_ts(raw: Any) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _load_evolution_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    rows.append(parsed)
    except OSError:
        return []
    return rows


def window_metrics(
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    window_days: int,
) -> dict[str, float]:
    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=window_days)
    filtered = [r for r in rows if (_parse_ts(r.get("timestamp")) or now_utc) >= cutoff]

    pnl = _coerce_float(summary.get("pnl_realized"))
    trades = _coerce_int(summary.get("total_trades"))
    wins = _coerce_int(summary.get("wins"))
    sharpe_values: list[float] = []
    summary_sharpe = _coerce_float(summary.get("sharpe_annualized"))
    if summary_sharpe != 0.0:
        sharpe_values.append(summary_sharpe)
    risk_events = _coerce_int(summary.get("risk_events"))

    for row in filtered:
        meta_raw = row.get("meta_review")
        meta = meta_raw if isinstance(meta_raw, dict) else {}
        pnl += _coerce_float(meta.get("net_pnl"))
        trades += _coerce_int(meta.get("trades"))
        wins += _coerce_int(meta.get("wins"))
        row_sharpe = _coerce_float(meta.get("sharpe"))
        if row_sharpe != 0.0:
            sharpe_values.append(row_sharpe)
        risk_events += _coerce_int(row.get("risk_events"))

    win_rate = (wins / trades) if trades > 0 else 0.0
    sharpe = (sum(sharpe_values) / len(sharpe_values)) if sharpe_values else 0.0
    return {
        "pnl": round(pnl, 2),
        "win_rate": round(win_rate, 6),
        "sharpe": round(sharpe, 4),
        "risk_events": float(risk_events),
    }


def build_real_ops_block(
    *,
    runtime: dict[str, Any],
    state_dir: Path,
) -> dict[str, Any] | None:
    summary = _load_json(state_dir / "last_run_summary.json")
    evo_path = state_dir / "evolution_log.jsonl"
    evolution_rows = _load_evolution_rows(evo_path)
    if not summary and not runtime:
        return None

    m24 = window_metrics(summary, evolution_rows, 1)
    m7 = window_metrics(summary, evolution_rows, 7)
    m30 = window_metrics(summary, evolution_rows, 30)

    risk_events = _coerce_int(summary.get("risk_events"))
    var_breaches = _coerce_int(summary.get("var_breach_count"))
    max_drawdown = _coerce_float(summary.get("max_drawdown"))
    sharpe = _coerce_float(summary.get("sharpe_annualized"))
    win_rate = _coerce_float(summary.get("win_rate"))
    session_guard_blocks = _coerce_int(summary.get("session_guard_blocks"))
    realized_pnl = _coerce_float(summary.get("pnl_realized"))
    total_trades = _coerce_int(summary.get("total_trades"))

    live_qty = _coerce_int(runtime.get("live_position_qty"))
    pending = _coerce_int(runtime.get("pending_reconciliations"))

    drawdown_ok = max_drawdown <= 500.0
    sharpe_ok = sharpe >= 1.0
    risk_events_ok = risk_events == 0
    var_ok = var_breaches == 0
    pnl_24h_ok = m24["pnl"] >= 0.0
    protocol_green = risk_events_ok and var_ok and drawdown_ok and sharpe_ok and pnl_24h_ok

    return {
        "realized_pnl": realized_pnl,
        "max_drawdown_usd": max_drawdown,
        "risk_events": risk_events,
        "var_breach_count": var_breaches,
        "win_rate": win_rate,
        "sharpe_annualized": sharpe,
        "session_guard_blocks": session_guard_blocks,
        "total_trades": total_trades,
        "window_pnl": {"h24": m24["pnl"], "d7": m7["pnl"], "d30": m30["pnl"]},
        "exposure": {
            "live_position_qty": live_qty,
            "pending_reconciliations": pending,
        },
        "capital_preservation": {
            "protocol_green": protocol_green,
            "gates": {
                "risk_events_zero": risk_events_ok,
                "var_breaches_zero": var_ok,
                "drawdown_under_500": drawdown_ok,
                "sharpe_at_least_1": sharpe_ok,
                "pnl_24h_non_negative": pnl_24h_ok,
            },
        },
    }
