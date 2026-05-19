"""Build live trading snapshot for core WebSocket telemetry."""

from __future__ import annotations

import json
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


def _normalize_trade_row(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        "ts": raw.get("ts"),
        "signal": str(raw.get("signal", "") or ""),
        "entry": _coerce_float(raw.get("entry")),
        "exit": _coerce_float(raw.get("exit")),
        "qty": _coerce_int(raw.get("qty")),
        "pnl": _coerce_float(raw.get("pnl")),
        "confluence": _coerce_float(raw.get("confluence")),
    }


def _load_latest_decision(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    last_row: dict[str, Any] | None = None
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    last_row = parsed
    except OSError:
        return None
    if not last_row:
        return None
    raw_output = last_row.get("raw_output")
    output_summary = ""
    if isinstance(raw_output, dict):
        output_summary = str(raw_output.get("summary") or raw_output.get("reason") or "")[:280]
    elif raw_output is not None:
        output_summary = str(raw_output)[:280]
    return {
        "timestamp": last_row.get("timestamp"),
        "agent_id": last_row.get("agent_id"),
        "confidence": _coerce_float(last_row.get("confidence")),
        "policy_outcome": str(last_row.get("policy_outcome") or ""),
        "decision_context_id": str(last_row.get("decision_context_id") or ""),
        "output_summary": output_summary,
    }


def build_live_trading_block(
    *,
    runtime: dict[str, Any],
    sim_state: dict[str, Any],
    regime_summary: dict[str, Any],
    state_dir: Path,
) -> dict[str, Any] | None:
    has_runtime = bool(runtime)
    has_sim = bool(sim_state)
    if not has_runtime and not has_sim:
        return None

    dream = sim_state.get("current_dream") if isinstance(sim_state.get("current_dream"), dict) else {}
    snapshot = sim_state.get("state_snapshot") if isinstance(sim_state.get("state_snapshot"), dict) else {}
    position_snap = snapshot.get("position") if isinstance(snapshot.get("position"), dict) else {}
    risk_snap = snapshot.get("risk") if isinstance(snapshot.get("risk"), dict) else {}
    agent_snap = snapshot.get("agent") if isinstance(snapshot.get("agent"), dict) else {}

    live_qty = _coerce_int(runtime.get("live_position_qty"), _coerce_int(sim_state.get("live_position_qty")))
    sim_qty = _coerce_int(sim_state.get("sim_position_qty"), _coerce_int(position_snap.get("sim_position_qty")))
    entry_price = _coerce_float(
        sim_state.get("last_entry_price"),
        _coerce_float(position_snap.get("last_entry_price")),
    )
    side_signal = str(sim_state.get("live_trade_signal") or position_snap.get("live_trade_signal") or "")
    daily_pnl = _coerce_float(runtime.get("daily_pnl"), _coerce_float(risk_snap.get("realized_pnl_today")))
    open_pnl = _coerce_float(runtime.get("open_pnl"), _coerce_float(risk_snap.get("open_pnl")))
    consecutive_losses = _coerce_int(runtime.get("consecutive_losses"))
    pending_reconciliations = _coerce_int(
        runtime.get("pending_reconciliations"),
        _coerce_int(risk_snap.get("pending_reconciliations")),
    )

    last_trades_raw = runtime.get("last_trades")
    last_trades: list[dict[str, Any]] = []
    if isinstance(last_trades_raw, list):
        for row in last_trades_raw[-10:]:
            normalized = _normalize_trade_row(row)
            if normalized:
                last_trades.append(normalized)

    regime_confidence = _coerce_float(regime_summary.get("regime_confidence"))

    active_signal = {
        "signal": str(dream.get("signal") or "HOLD"),
        "confidence": _coerce_float(dream.get("confidence"), _coerce_float(agent_snap.get("confidence"))),
        "confluence": _coerce_float(dream.get("confluence_score")),
        "reason": str(dream.get("reason") or ""),
        "why_no_trade": str(dream.get("why_no_trade") or ""),
        "stop": _coerce_float(dream.get("stop")),
        "target": _coerce_float(dream.get("target")),
        "strategy": str(dream.get("chosen_strategy") or agent_snap.get("chosen_strategy") or ""),
    }

    decision_path = state_dir / "agent_decision_log.jsonl"
    latest_decision = _load_latest_decision(decision_path)

    runtime_state: dict[str, Any] = {}
    if isinstance(sim_state, dict):
        runtime_state = {
            k: sim_state.get(k)
            for k in (
                "sim_position_qty",
                "live_position_qty",
                "live_trade_signal",
                "last_entry_price",
                "pending_trade_reconciliations",
            )
            if k in sim_state
        }

    return {
        "position": {
            "live_qty": live_qty,
            "sim_qty": sim_qty,
            "side_signal": side_signal,
            "entry_price": entry_price,
            "open_pnl": open_pnl,
            "daily_pnl": daily_pnl,
        },
        "active_signal": active_signal,
        "regime_confidence": regime_confidence,
        "consecutive_losses": consecutive_losses,
        "pending_reconciliations": pending_reconciliations,
        "last_trades": last_trades,
        "latest_decision": latest_decision,
        "current_dream": dream if dream else None,
        "runtime_state": runtime_state if runtime_state else None,
    }
