"""Supervisor tick phase blocks — preflight / signal-gate / exec / post-monitor.

Extracted from SupervisorPhaseStateMachine (Wave B3 PR-D0). Behavior-preserving;
SM remains the thin dispatcher façade.
"""

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


def run_tick_exec(sm: Any, ctx: SupervisorTickCtx) -> None:
    """Paper/real execution, open PnL, sim hit-close with legacy fallback."""
    app = sm.app
    engine = sm.engine
    dream_snapshot = ctx.dream_snapshot if isinstance(ctx.dream_snapshot, dict) else {}
    signal = ctx.signal
    trade_mode = ctx.trade_mode
    min_confluence = ctx.min_confluence
    qty_multiplier = ctx.qty_multiplier
    stop_widen_multiplier = ctx.stop_widen_multiplier
    price = ctx.price
    _cfg = ctx.cfg
    swarm_manager = ctx.swarm_manager
    _push_trader_league_trade = ctx.push_trader_league_trade

    skip_exec = False
    if signal in ["BUY", "SELL"] and dream_snapshot.get("confluence_score", 0) > min_confluence:
        regime = dream_snapshot.get("regime", "NEUTRAL")
        stop_price = float(dream_snapshot.get("stop", price * 0.99 if signal == "BUY" else price * 1.01))
        widened_dist = abs(price - stop_price) * max(1.0, stop_widen_multiplier)
        stop_price = price - widened_dist if signal == "BUY" else price + widened_dist
        qty = app.calculate_adaptive_risk_and_qty(
            price,
            regime,
            stop_price,
            confidence=float(dream_snapshot.get("confluence_score", 0.0) or 0.0),
        )
        if qty <= 0:
            sm._logger.warning(
                f"REAL_POSITION_FLOOR_HOLD,reason=insufficient_risk_budget,signal={signal},regime={regime}"
            )
            signal = "HOLD"
            qty = 0
            skip_exec = True
        else:
            qty = max(1, int(qty * max(0.1, qty_multiplier)))

        if not skip_exec:
            if runtime_trace_enabled():
                log_runtime_trace(
                    sm._logger,
                    "supervisor.execution_armed",
                    trade_mode=trade_mode,
                    signal=str(signal),
                    qty=int(qty),
                    stop=round(float(stop_price), 4),
                    conf=round(float(dream_snapshot.get("confluence_score", 0) or 0), 4),
                )

            if trade_mode == "paper":
                if getattr(app, "sim_position_qty", 0) == 0:
                    container = getattr(app, "container", None)
                    broker = getattr(container, "broker", None) if container is not None else None
                    inst = PriceDupeResolver(app=app).paper_instrument()
                    simulator = PaperSimulator(
                        app=app,
                        broker=broker,
                        container=container,
                        valuation_engine=sm.valuation_engine,
                    )
                    simulator.try_open(
                        signal=str(signal),
                        qty=int(qty),
                        dream_snapshot=dream_snapshot,
                        inst=inst,
                        regime=str(regime),
                    )
            else:
                if hasattr(app, "place_order") and app.place_order(signal, qty):
                    log_structured(
                        LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_LEARNING,
                            code="INFO_PRINT_LEGACY",
                            message=f"✅ {trade_mode.upper()} {signal} {qty}x @ {price:.2f} (regime-adapted)",
                            context={"mode": trade_mode, "signal": signal, "qty": qty},
                        )
                    )

    if trade_mode == "paper":
        simulator = PaperSimulator(
            app=app,
            broker=getattr(getattr(app, "container", None), "broker", None),
            container=getattr(app, "container", None),
            valuation_engine=sm.valuation_engine,
        )
        if hasattr(app, "open_pnl"):
            app.open_pnl = simulator.get_open_pnl(float(price))
    else:
        if hasattr(app, "open_pnl"):
            app.open_pnl = getattr(app, "account_equity", 0) - getattr(app, "account_balance", 0)

    if getattr(app, "sim_position_qty", 0) != 0:
        stop = dream_snapshot.get("stop", 0)
        target = dream_snapshot.get("target", 0)
        sim_qty = int(getattr(app, "sim_position_qty", 0) or 0)
        hit_stop = (sim_qty > 0 and price <= stop) or (sim_qty < 0 and price >= stop)
        hit_target = (sim_qty > 0 and price >= target) or (sim_qty < 0 and price <= target)

        if hit_stop or hit_target:
            container = getattr(app, "container", None)
            broker = getattr(container, "broker", None) if container is not None else None
            simulator = PaperSimulator(
                app=app,
                broker=broker,
                container=container,
                valuation_engine=sm.valuation_engine,
            )
            close_handled = simulator.check_close(price=float(price), dream_snapshot=dream_snapshot)
            if not close_handled:
                inst = PriceDupeResolver(app=app).paper_instrument()
                sym_ve = str(inst)
                pnl_dollars = sm.valuation_engine.pnl_dollars(
                    symbol=sym_ve,
                    entry_price=float(getattr(app, "sim_entry_price", 0.0) or 0.0),
                    exit_price=float(price),
                    side=1 if sim_qty > 0 else -1,
                    quantity=abs(sim_qty),
                )
                if hasattr(app, "pnl_history"):
                    app.pnl_history.append(pnl_dollars)
                if getattr(app, "equity_curve", None):
                    app.equity_curve.append(app.equity_curve[-1] + pnl_dollars)
                if getattr(app, "equity_curve", None) and app.equity_curve[-1] > getattr(app, "sim_peak", 0):
                    app.sim_peak = app.equity_curve[-1]

                entry_snap = float(getattr(app, "sim_entry_price", 0.0) or 0.0)
                exit_fill_price = float(price)
                closed_qty = abs(sim_qty)
                regime = dream_snapshot.get("regime", "NEUTRAL")
                if hasattr(app, "update_performance_log"):
                    app.update_performance_log(
                        {
                            "signal": dream_snapshot.get("signal"),
                            "chosen_strategy": dream_snapshot.get("chosen_strategy"),
                            "regime": regime,
                            "confluence": dream_snapshot.get("confluence_score", 0),
                            "pnl": pnl_dollars,
                            "drawdown": (app.sim_peak - app.equity_curve[-1]) / app.sim_peak
                            if getattr(app, "sim_peak", 0)
                            else 0,
                        }
                    )

                publish_fn = getattr(app, "publish_traderleague_trade_close", None)
                if callable(publish_fn):
                    try:
                        latest_reflection = ""
                        if getattr(app, "trade_reflection_history", None):
                            latest_reflection = str(app.trade_reflection_history[-1].get("reflection", ""))
                        publish_fn(
                            symbol=str(getattr(app, "INSTRUMENT", getattr(_cfg, "instrument", "MES"))),
                            entry_price=float(entry_snap),
                            exit_price=float(exit_fill_price),
                            quantity=int(closed_qty),
                            pnl=float(pnl_dollars),
                            reflection=latest_reflection,
                            chart_snapshot_url=str(getattr(app, "current_live_chart_file", "") or ""),
                        )
                    except Exception as exc:
                        err = LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                            code="RUNTIME_LEAGUE_014",
                            message=str(exc),
                            context={"traceback": traceback.format_exc()},
                        )
                        log_structured(err)
                        sm._logger.error(f"TraderLeague publish error: {exc}")

                if swarm_manager is not None and hasattr(swarm_manager, "register_trade_result"):
                    try:
                        symbol = getattr(app, "INSTRUMENT", getattr(_cfg, "instrument", "MES"))
                        swarm_manager.register_trade_result(symbol, pnl_dollars)
                    except Exception as exc:
                        err = LuminaError(
                            severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                            code="RUNTIME_SWARM_015",
                            message=str(exc),
                            context={"traceback": traceback.format_exc()},
                        )
                        log_structured(err)
                        sm._logger.error(f"Swarm trade register error: {exc}")

                if trade_mode == "paper" and _push_trader_league_trade is not None:
                    _push_trader_league_trade(
                        app,
                        mode=trade_mode,
                        symbol=str(getattr(app, "INSTRUMENT", getattr(_cfg, "instrument", "MES"))),
                        signal=str(dream_snapshot.get("signal")),
                        entry_price=float(entry_snap),
                        exit_price=float(exit_fill_price),
                        qty=int(closed_qty),
                        pnl_dollars=float(pnl_dollars),
                        reflection={},
                        chart_base64=None,
                    )

                if trade_mode != "paper":
                    LivePositionManager(app=app).reset_all()
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="INFO_PRINT_LEGACY",
                        message=f"🎯 TRADE CLOSED → {'WIN' if pnl_dollars > 0 else 'LOSS'} ${pnl_dollars:.0f}",
                        context={"pnl": pnl_dollars, "mode": trade_mode},
                    )
                )

                try:
                    lock = getattr(app, "live_data_lock", None)
                    if lock is not None and hasattr(app, "ohlc_1min"):
                        with lock:
                            bt_snapshot = app.ohlc_1min.tail(500).copy()
                        if len(bt_snapshot) >= 60 and engine is not None and hasattr(engine, "backtester"):
                            bt_result = engine.backtester.run_backtest_on_snapshot(bt_snapshot)
                            if hasattr(app, "log_thought"):
                                app.log_thought(
                                    {"type": "trade_reflection_backtest", "pnl": pnl_dollars, "backtest": bt_result}
                                )
                            log_structured(
                                LuminaError(
                                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                                    code="INFO_PRINT_LEGACY",
                                    message=(
                                        f"🔬 POST-TRADE BACKTEST → "
                                        f"Sharpe {bt_result['sharpe']:.2f} | WR {bt_result['winrate']:.1%} | "
                                        f"MaxDD {bt_result['maxdd']:.1f}% | AvgPnL ${bt_result['avg_pnl']:.1f}"
                                    ),
                                    context={"pnl": pnl_dollars, "backtest": bt_result},
                                )
                            )
                except Exception as exc:
                    err = LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RUNTIME_BACKTEST_016",
                        message=str(exc),
                        context={"traceback": traceback.format_exc()},
                    )
                    log_structured(err)
                    sm._logger.error(f"Post-trade backtest error: {exc}")

    ctx.signal = signal
    ctx.dream_snapshot = dream_snapshot


def run_tick_post_monitor(sm: Any, ctx: SupervisorTickCtx) -> None:
    """Swarm dashboard, status, oracle KPIs, save_state, monitoring snapshot."""
    app = sm.app
    engine = sm.engine
    dream_snapshot = ctx.dream_snapshot if isinstance(ctx.dream_snapshot, dict) else {}
    trade_mode = ctx.trade_mode
    rl_action = ctx.rl_action
    _cfg = ctx.cfg
    swarm_manager = ctx.swarm_manager
    _compute_session_kpis = ctx.compute_session_kpis
    _publish_runtime_monitoring_snapshot = ctx.publish_runtime_monitoring_snapshot

    if swarm_manager is not None and time.time() - sm._swarm_last_dashboard >= 60:
        try:
            dashboard_path = swarm_manager.generate_dashboard_plot()
            if dashboard_path and hasattr(app, "set_current_dream_value"):
                app.set_current_dream_value("swarm_dashboard_path", dashboard_path)
            sm._swarm_last_dashboard = time.time()
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="RUNTIME_SWARM_017",
                message=str(exc),
                context={"traceback": traceback.format_exc()},
            )
            log_structured(err)
            sm._logger.error(f"Swarm dashboard error: {exc}")

    mode_text = {"paper": "PAPER (internal sim)", "sim": "SIM (real orders on demo)", "real": "REAL MONEY"}.get(
        trade_mode, trade_mode.upper()
    )
    status_interval = float(getattr(_cfg, "status_print_interval_sec", 60) or 60)
    if time.time() - sm._last_status_print >= status_interval:
        rl_bias_str = ""
        if isinstance(rl_action, dict):
            rl_bias_str = f" | RL {int(rl_action.get('signal', 0))}:{float(rl_action.get('qty_pct', 1.0)):.2f}"
        sm._logger.info(
            f"Status [{mode_text}] | Equity ${getattr(app, 'account_equity', 0):,.0f} | "
            f"Open PnL ${getattr(app, 'open_pnl', 0):,.0f} | Realized ${getattr(app, 'realized_pnl_today', 0):,.0f} | "
            f"Conf {dream_snapshot.get('confluence_score', 0):.2f}{rl_bias_str}"
        )
        sm._last_status_print = time.time()

    if time.time() - sm._last_infinite_sim_status >= 1800:
        inf_sim = getattr(engine, "infinite_simulator", None) if engine is not None else None
        if inf_sim is not None:
            sm._logger.info("INFINITE_SIM_MONITOR,status=ready")
        sm._last_infinite_sim_status = time.time()

    if (
        time.time() - sm._last_oracle > 60
        and len(getattr(app, "pnl_history", []) or []) > 5
        and _compute_session_kpis is not None
    ):
        kpis = _compute_session_kpis(app)
        np_mod = getattr(app, "np", None)
        pnl_hist = getattr(app, "pnl_history", []) or []
        expectancy = float(np_mod.mean(pnl_hist)) if np_mod is not None and pnl_hist else 0.0
        sm._logger.info(
            f"ORACLE metrics | Sharpe {kpis['sharpe_annualized']:.2f} | Expected ${expectancy:.0f} | "
            f"Winrate {kpis['winrate']:.1%} | PF {kpis['profit_factor']:.2f} | "
            f"MaxDD {kpis['max_drawdown_pct']:.1f}%"
        )

    if time.time() - sm._last_save > 30:
        try:
            app.save_state()
            sm._logger.info("STATE_SAVED,status=ok")
        except Exception as _save_exc:
            sm._logger.error(f"STATE_SAVE_FAILED: {_save_exc}\n{traceback.format_exc()}")
        sm._last_save = time.time()

    if time.time() - sm._last_monitoring_snapshot > 15:
        try:
            if _publish_runtime_monitoring_snapshot is not None:
                _publish_runtime_monitoring_snapshot(app)
        except Exception as exc:
            sm._logger.warning(f"MONITORING_SNAPSHOT_WRITE_FAILED: {exc}")
        sm._last_monitoring_snapshot = time.time()
