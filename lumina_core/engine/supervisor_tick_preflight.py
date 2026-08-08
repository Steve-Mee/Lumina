"""supervisor_tick_preflight."""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.engine.eod_force_close_service import EODForceCloseService
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.engine.paper_simulator import PaperSimulator
from lumina_core.engine.price_dupe_resolver import PriceDupeResolver
from lumina_core.engine.real_close_detector import RealCloseDetector
from lumina_core.engine.rl_bias_applier import RlBiasApplier
from lumina_core.logging_utils import log_runtime_trace, runtime_trace_enabled
from lumina_core.reasoning.agent_contracts import apply_agent_policy_gateway
from lumina_core.runtime_trade_gates import apply_hard_risk_controller_to_signal


@dataclass
class SupervisorTickCtx:
    """Mutable per-tick state shared across phase blocks."""

    price: float
    dream_snapshot: dict[str, Any] | None
    now: datetime
    gate_result: dict[str, Any] = field(default_factory=dict)
    rl_action: Any = None
    eod_force_hold: bool = False
    min_confluence: float = 0.0
    signal: str = "HOLD"
    trade_mode: str = "paper"
    qty_multiplier: float = 1.0
    stop_widen_multiplier: float = 1.0
    hold_until_ts: float = 0.0
    swarm_manager: Any = None
    cfg: Any = None
    push_trader_league_trade: Callable[..., Any] | None = None
    compute_session_kpis: Callable[..., Any] | None = None
    publish_runtime_monitoring_snapshot: Callable[..., Any] | None = None


def run_tick_preflight(sm: Any, ctx: SupervisorTickCtx) -> None:
    """Validator, balance, real close/DD kill, EOD, twin, swarm cycle."""
    app = sm.app
    engine = sm.engine
    now = ctx.now
    dream_snapshot = ctx.dream_snapshot

    if dream_snapshot is None and hasattr(app, "get_current_dream_snapshot"):
        dream_snapshot = app.get_current_dream_snapshot()
    if dream_snapshot is None:
        dream_snapshot = {}

    validator = getattr(engine, "validator", None) if engine is not None else None
    last_validation = getattr(engine, "last_validation", None) if engine is not None else sm._last_validation
    if validator is not None and hasattr(validator, "run_3year_validation"):
        should_run_validation = last_validation is None or (now - last_validation).days >= 30
        if should_run_validation:
            try:
                validator.run_3year_validation()
                if engine is not None:
                    engine.last_validation = now
                sm._last_validation = now
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RUNTIME_VALIDATOR_011",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                sm._logger.error(f"Periodic validator run failed: {exc}")

    if time.time() - sm._last_balance_fetch > 10:
        _ops = getattr(getattr(app, "container", None), "operations_service", None)
        if _ops is not None:
            _ops.fetch_account_balance()
        sm._last_balance_fetch = time.time()

    _cfg = getattr(engine, "config", None) if engine is not None else None
    trade_mode = str(getattr(_cfg, "trade_mode", "paper") or "paper")

    if trade_mode == "real":
        RealCloseDetector(
            app=app, reconciler=getattr(app, "trade_reconciler", None)
        ).detect_and_handle(float(ctx.price))

    if trade_mode == "real":
        dd_pct = float(getattr(_cfg, "drawdown_kill_percent", 0) or 0)
        if getattr(app, "account_equity", 0) < getattr(app, "account_balance", 0) * (1 - dd_pct / 100):
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                    code="RUNTIME_DRAWDOWN_KILL",
                    message=f"🚨 REAL DRAWDOWN KILL ({dd_pct}%) - STOPPING",
                    context={"mode": "real"},
                )
            )
            app.save_state()
            raise SystemExit("Drawdown kill - real money")

    eod_closer = EODForceCloseService(
        app=app,
        broker=getattr(getattr(app, "container", None), "broker", None),
        container=getattr(app, "container", None),
    )
    eod_force_hold = bool(eod_closer.enforce_eod_force_close(float(ctx.price)))

    if hasattr(app, "get_current_dream_snapshot"):
        dream_snapshot = app.get_current_dream_snapshot()
    twin = getattr(engine, "emotional_twin", None) if engine is not None else None
    if twin is not None and hasattr(twin, "apply_correction"):
        dream_snapshot = twin.apply_correction(dream_snapshot)
        if hasattr(app, "set_current_dream_fields"):
            app.set_current_dream_fields(dream_snapshot)

    swarm_manager = getattr(app, "swarm_manager", None) or (
        getattr(engine, "swarm", None) if engine is not None else None
    )
    current_swarm_minute = (now.year, now.month, now.day, now.hour, now.minute)
    should_run_swarm = (
        swarm_manager is not None
        and int(now.minute) % 5 == 0
        and sm._swarm_last_cycle_minute != current_swarm_minute
    )
    if should_run_swarm:
        try:
            swarm_info = swarm_manager.run_swarm_cycle()
            swarm_manager.apply_to_primary_dream()
            if isinstance(swarm_info, dict) and hasattr(app, "set_current_dream_fields"):
                app.set_current_dream_fields(
                    {
                        "swarm_regime": swarm_info.get("global_regime", "NEUTRAL"),
                        "swarm_allocation": swarm_info.get("allocation", {}),
                    }
                )
            if hasattr(app, "get_current_dream_snapshot"):
                dream_snapshot = app.get_current_dream_snapshot()
            sm._swarm_last_cycle = time.time()
            sm._swarm_last_cycle_minute = current_swarm_minute
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="RUNTIME_SWARM_013",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            sm._logger.error(f"Swarm cycle error: {exc}")

    ctx.dream_snapshot = dream_snapshot if isinstance(dream_snapshot, dict) else {}
    ctx.eod_force_hold = eod_force_hold
    ctx.trade_mode = trade_mode
    ctx.cfg = _cfg
    ctx.swarm_manager = swarm_manager
