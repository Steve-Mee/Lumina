"""Build trading performance snapshot for core WebSocket telemetry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _coerce_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_jsonl_tail(path: Path, *, limit: int = 30) -> list[dict[str, Any]]:
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
    return rows[-limit:]


def _compute_kpis_from_series(
    *,
    pnl_history: list[float],
    equity_curve: list[float],
) -> dict[str, float]:
    winrate = 0.0
    if pnl_history:
        wins = sum(1 for p in pnl_history if p > 0)
        winrate = wins / len(pnl_history)

    sharpe = 0.0
    tail = pnl_history[-50:]
    if len(tail) > 1:
        mean = sum(tail) / len(tail)
        variance = sum((p - mean) ** 2 for p in tail) / len(tail)
        std = variance**0.5
        sharpe = (mean / (std + 1e-8)) * (252**0.5)

    profit_factor = 0.0
    if any(p < 0 for p in pnl_history):
        gross_profit = sum(p for p in pnl_history if p > 0)
        gross_loss = sum(abs(p) for p in pnl_history if p < 0)
        profit_factor = abs(gross_profit / (gross_loss + 1e-8))

    max_drawdown_pct = 0.0
    max_drawdown_usd = 0.0
    if len(equity_curve) > 1:
        peak = equity_curve[0]
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown_usd:
                max_drawdown_usd = drawdown
            if peak > 0:
                dd_pct = (drawdown / peak) * 100.0
                if dd_pct > max_drawdown_pct:
                    max_drawdown_pct = dd_pct

    return {
        "winrate": round(winrate, 6),
        "sharpe_annualized": round(sharpe, 4),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown_pct": round(-max_drawdown_pct, 4),
        "max_drawdown_usd": round(max_drawdown_usd, 2),
        "realized_pnl_session": round(sum(pnl_history), 2) if pnl_history else 0.0,
    }


def _parse_float_series(raw: Any) -> list[float]:
    if not isinstance(raw, list):
        return []
    out: list[float] = []
    for item in raw:
        val = _coerce_float(item)
        if val is not None:
            out.append(val)
    return out


def _resolve_session_kpis(
    *,
    runtime: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, float]:
    session_raw = runtime.get("session_kpis")
    if isinstance(session_raw, dict) and session_raw:
        return {
            "winrate": float(_coerce_float(session_raw.get("winrate"), 0.0) or 0.0),
            "sharpe_annualized": float(
                _coerce_float(session_raw.get("sharpe_annualized"), 0.0) or 0.0
            ),
            "profit_factor": float(_coerce_float(session_raw.get("profit_factor"), 0.0) or 0.0),
            "max_drawdown_pct": float(
                _coerce_float(session_raw.get("max_drawdown_pct"), 0.0) or 0.0
            ),
            "max_drawdown_usd": float(
                _coerce_float(session_raw.get("max_drawdown_usd"), 0.0) or 0.0
            ),
            "realized_pnl_session": float(
                _coerce_float(session_raw.get("realized_pnl_session"), 0.0) or 0.0
            ),
        }

    pnl_history = _parse_float_series(runtime.get("pnl_history"))
    equity_curve = _parse_float_series(runtime.get("equity_curve"))
    if pnl_history or len(equity_curve) > 1:
        return _compute_kpis_from_series(pnl_history=pnl_history, equity_curve=equity_curve)

    return {
        "winrate": float(_coerce_float(summary.get("win_rate"), 0.0) or 0.0),
        "sharpe_annualized": float(_coerce_float(summary.get("sharpe_annualized"), 0.0) or 0.0),
        "profit_factor": float(_coerce_float(summary.get("profit_factor"), 0.0) or 0.0),
        "max_drawdown_pct": float(_coerce_float(summary.get("max_drawdown_pct"), 0.0) or 0.0),
        "max_drawdown_usd": float(_coerce_float(summary.get("max_drawdown"), 0.0) or 0.0),
        "realized_pnl_session": float(_coerce_float(summary.get("pnl_realized"), 0.0) or 0.0),
    }


def build_performance_block(
    *,
    runtime: dict[str, Any],
    state_dir: Path,
) -> dict[str, Any] | None:
    summary_path = state_dir / "last_run_summary.json"
    summary: dict[str, Any] = {}
    if summary_path.is_file():
        try:
            parsed = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                summary = parsed
        except (OSError, json.JSONDecodeError):
            summary = {}

    has_runtime = bool(runtime)
    has_summary = bool(summary)
    if not has_runtime and not has_summary:
        return None

    equity_curve = _parse_float_series(runtime.get("equity_curve"))
    equity_series = [{"t": idx, "equity": val} for idx, val in enumerate(equity_curve)]

    daily_rows = _load_jsonl_tail(state_dir / "monitoring_daily_pnl.jsonl", limit=30)
    daily_history: list[dict[str, Any]] = []
    for idx, row in enumerate(daily_rows):
        daily_pnl = _coerce_float(row.get("daily_pnl"))
        if daily_pnl is None:
            continue
        daily_history.append(
            {
                "t": idx,
                "daily_pnl": daily_pnl,
                "ts": row.get("timestamp") or row.get("ts"),
            }
        )

    session_kpis = _resolve_session_kpis(runtime=runtime, summary=summary)
    source = "live" if has_runtime and (equity_curve or runtime.get("session_kpis")) else "fallback"

    return {
        "source": source,
        "account_equity": _coerce_float(runtime.get("account_equity")),
        "daily_pnl": _coerce_float(runtime.get("daily_pnl"), 0.0) or 0.0,
        "open_pnl": _coerce_float(runtime.get("open_pnl"), 0.0) or 0.0,
        "session_kpis": session_kpis,
        "equity_series": equity_series,
        "daily_history": daily_history,
    }
