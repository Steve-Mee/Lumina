"""supervisor_tick_signal."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.rl_bias_applier import RlBiasApplier
from lumina_core.engine.supervisor_tick_ctx import SupervisorTickCtx
from lumina_core.logging_utils import log_runtime_trace, runtime_trace_enabled
from lumina_core.reasoning.agent_contracts import apply_agent_policy_gateway
from lumina_core.runtime_trade_gates import apply_hard_risk_controller_to_signal


def run_tick_signal_gate(sm: Any, ctx: SupervisorTickCtx) -> None:
    """Dream signal, RL bias, arb/hold, hard risk, agent policy gateway."""
    app = sm.app
    engine = sm.engine
    dream_snapshot = ctx.dream_snapshot if isinstance(ctx.dream_snapshot, dict) else {}
    _cfg = ctx.cfg
    trade_mode = ctx.trade_mode
    eod_force_hold = ctx.eod_force_hold
    price = ctx.price

    hold_until_ts = float(dream_snapshot.get("hold_until_ts", 0.0) or 0.0)
    min_confluence = float(
        dream_snapshot.get("min_confluence_override", getattr(_cfg, "min_confluence", 0.0))
        or getattr(_cfg, "min_confluence", 0.0)
    )
    from lumina_core.code_evolution.runtime_overlay import (
        effective_min_confluence,
        overlay_from_engine,
    )

    min_confluence = effective_min_confluence(min_confluence, overlay_from_engine(engine))
    qty_multiplier = float(dream_snapshot.get("position_size_multiplier", 1.0) or 1.0)
    stop_widen_multiplier = float(dream_snapshot.get("stop_widen_multiplier", 1.0) or 1.0)
    signal = dream_snapshot.get("signal", "HOLD")
    if eod_force_hold:
        signal = "HOLD"
        if isinstance(dream_snapshot, dict):
            dream_snapshot["signal"] = "HOLD"
            dream_snapshot["why_no_trade"] = "REAL EOD force-close/no-new-trades window active"

    baseline_signal = str(signal)
    rl_bias = RlBiasApplier(app=app)
    signal, rl_action, qty_multiplier, stop_widen_multiplier = rl_bias.apply_bias(
        current_signal=signal,
        dream_snapshot=dream_snapshot,
        qty_multiplier=qty_multiplier,
        stop_widen_multiplier=stop_widen_multiplier,
        baseline_signal=baseline_signal,
    )

    if signal == "HOLD":
        arb_signal = str(dream_snapshot.get("swarm_arb_signal", "HOLD")).upper()
        if arb_signal in {"BUY", "SELL"}:
            signal = arb_signal

    if hasattr(app, "is_market_open") and not app.is_market_open():
        signal = "HOLD"
    if hold_until_ts > time.time():
        signal = "HOLD"

    _risk_ctrl = getattr(engine, "risk_controller", None) if engine is not None else None
    _inst = getattr(_cfg, "instrument", None) if _cfg is not None else None
    _instrument = str(getattr(app, "INSTRUMENT", None) or _inst or "MES")
    signal, _risk_ok, _risk_reason = apply_hard_risk_controller_to_signal(
        signal=str(signal),
        price=float(price),
        dream_snapshot=dream_snapshot,
        instrument=_instrument,
        risk_controller=_risk_ctrl,
        logger=sm._logger,
        mode=trade_mode.strip().lower(),
        engine=engine,
    )

    session_allowed = True
    if signal in {"BUY", "SELL"} and not _risk_ok:
        session_allowed = not str(_risk_reason).startswith("Session guard blocked")

    risk_allowed = bool(signal == "HOLD")
    if signal in ["BUY", "SELL"]:
        risk_allowed = bool(_risk_ok)

    gate_result = apply_agent_policy_gateway(
        signal=str(signal),
        confluence_score=float(dream_snapshot.get("confluence_score", 0.0) or 0.0),
        min_confluence=float(min_confluence),
        hold_until_ts=float(hold_until_ts),
        mode=trade_mode.strip().lower(),
        session_allowed=bool(session_allowed),
        risk_allowed=bool(risk_allowed),
        lineage={
            "model_identifier": str(dream_snapshot.get("chosen_strategy", "runtime-supervisor")),
            "prompt_version": "runtime-supervisor-v1",
            "prompt_hash": "runtime-supervisor",
            "policy_version": "agent-policy-gateway-v1",
            "provider_route": [
                str(getattr(getattr(engine, "local_engine", None), "active_provider", "unknown-provider"))
                if getattr(engine, "local_engine", None) is not None
                else "unknown-provider"
            ],
            "calibration_factor": 1.0,
        },
    )
    signal = str(gate_result.get("signal", signal))

    if runtime_trace_enabled():
        _now_ts = time.time()
        _now_utc_iso = datetime.fromtimestamp(_now_ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _hut = float(hold_until_ts or 0.0)
        _hold_rem = max(0.0, _hut - _now_ts) if _hut > 0.0 else 0.0
        _hold_iso = ""
        if _hut > 0.0:
            try:
                _hold_iso = datetime.fromtimestamp(_hut, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except (OSError, ValueError, OverflowError):
                _hold_iso = "invalid_timestamp"
        log_runtime_trace(
            sm._logger,
            "supervisor.policy_gateway",
            trade_mode=trade_mode,
            price=round(float(price), 4),
            signal=str(signal),
            conf=round(float(dream_snapshot.get("confluence_score", 0) or 0), 4),
            min_conf=round(float(min_confluence), 4),
            gateway_reason=str(gate_result.get("reason", "")),
            gateway_approved=str(bool(gate_result.get("approved", False))),
            session_allowed=str(bool(session_allowed)),
            risk_allowed=str(bool(risk_allowed)),
            sim_qty=int(getattr(app, "sim_position_qty", 0) or 0),
            regime=str(dream_snapshot.get("regime", "") or ""),
            market_open=str(bool(app.is_market_open() if hasattr(app, "is_market_open") else True)),
            hold_until_ts=round(_hut, 3),
            hold_until_utc=_hold_iso,
            hold_sec_remaining=round(_hold_rem, 1),
            hold_window_active=str(bool(_hut > _now_ts)),
            now_epoch_s=round(_now_ts, 3),
            now_utc_iso=_now_utc_iso,
        )

    ctx.dream_snapshot = dream_snapshot
    ctx.signal = str(signal)
    ctx.rl_action = rl_action
    ctx.min_confluence = min_confluence
    ctx.gate_result = gate_result
    ctx.qty_multiplier = qty_multiplier
    ctx.stop_widen_multiplier = stop_widen_multiplier
    ctx.hold_until_ts = hold_until_ts
