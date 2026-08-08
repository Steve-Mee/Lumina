"""supervisor_tick_post."""
from __future__ import annotations

import time
import traceback
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.engine.supervisor_tick_ctx import SupervisorTickCtx


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
