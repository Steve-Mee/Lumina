"""supervisor_tick_exec."""
from __future__ import annotations

import traceback
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.engine.live_position_manager import LivePositionManager
from lumina_core.engine.paper_simulator import PaperSimulator
from lumina_core.engine.price_dupe_resolver import PriceDupeResolver
from lumina_core.engine.supervisor_tick_ctx import SupervisorTickCtx
from lumina_core.logging_utils import log_runtime_trace, runtime_trace_enabled


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
