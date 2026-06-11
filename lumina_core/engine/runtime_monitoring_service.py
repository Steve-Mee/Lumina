"""
RuntimeMonitoringService — D2 sub-slice 15: session KPI + monitoring snapshot from runtime_workers.

Observability-only; non-capital path. Same formulas as legacy ORACLE log block.
"""

from __future__ import annotations

from typing import Any

from lumina_core.logging_utils import write_runtime_monitoring_snapshot


class RuntimeMonitoringService:
    """Bounded owner for session KPIs and runtime monitoring snapshots (D2 sub-slice 15)."""

    def __init__(self, *, app: Any) -> None:
        self.app = app

    def compute_session_kpis(self) -> dict[str, float]:
        """Compute live session KPIs using the same formulas as the ORACLE log block."""
        app = self.app
        np = app.np
        pnl_history = list(getattr(app, "pnl_history", []) or [])
        equity_curve = list(getattr(app, "equity_curve", []) or [])

        winrate = float(np.mean(np.array(pnl_history) > 0)) if pnl_history else 0.0
        returns = np.array(pnl_history[-50:])
        sharpe = (
            (float(np.mean(returns)) / (float(np.std(returns)) + 1e-8)) * float(np.sqrt(252))
            if len(returns) > 1
            else 0.0
        )
        profit_factor = 0.0
        if any(p < 0 for p in pnl_history):
            gross_profit = sum(p for p in pnl_history if p > 0)
            gross_loss = sum(abs(p) for p in pnl_history if p < 0)
            profit_factor = abs(gross_profit / (gross_loss + 1e-8))

        max_drawdown_pct = 0.0
        max_drawdown_usd = 0.0
        if len(equity_curve) > 1:
            peak = np.maximum.accumulate(np.array(equity_curve, dtype=float))
            drawdowns = peak - np.array(equity_curve, dtype=float)
            max_drawdown_usd = float(np.max(drawdowns))
            with np.errstate(divide="ignore", invalid="ignore"):
                dd_pct = (drawdowns / peak) * 100.0
            max_drawdown_pct = float(np.min(dd_pct)) if dd_pct.size else 0.0

        realized_pnl_session = float(sum(pnl_history)) if pnl_history else 0.0

        return {
            "winrate": round(winrate, 6),
            "sharpe_annualized": round(sharpe, 4),
            "profit_factor": round(profit_factor, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "max_drawdown_usd": round(max_drawdown_usd, 2),
            "realized_pnl_session": round(realized_pnl_session, 2),
        }

    def publish_snapshot(self) -> None:
        app = self.app
        risk_controller = getattr(app.engine, "risk_controller", None)
        consecutive_losses = int(getattr(risk_controller, "consecutive_losses", 0) or 0)
        account_balance = float(getattr(app, "account_balance", 0.0) or 0.0)
        account_equity = float(getattr(app, "account_equity", 0.0) or 0.0)
        drawdown_pct = 0.0
        if account_balance > 0:
            drawdown_pct = max(0.0, (account_balance - account_equity) / account_balance * 100.0)

        mc_drawdown_pct = None
        if risk_controller is not None:
            rc_state = getattr(risk_controller, "state", None)
            if rc_state is not None:
                worst = getattr(rc_state, "mc_drawdown_worst_pct", None)
                if worst is not None:
                    mc_drawdown_pct = float(worst)

        drawdown_kill_pct = float(getattr(app.engine.config, "drawdown_kill_percent", 8.0) or 8.0)

        equity_curve = [float(v) for v in list(getattr(app, "equity_curve", []) or [])[-120:]]
        pnl_history = [float(v) for v in list(getattr(app, "pnl_history", []) or [])[-50:]]
        session_kpis = self.compute_session_kpis()

        payload = {
            "mode": str(getattr(app.engine.config, "trade_mode", "paper")).strip().lower(),
            "live_position_qty": int(getattr(app.engine, "live_position_qty", 0) or 0),
            "daily_pnl": float(getattr(app, "realized_pnl_today", 0.0) or 0.0),
            "open_pnl": float(getattr(app, "open_pnl", 0.0) or 0.0),
            "account_equity": account_equity,
            "account_balance": account_balance,
            "drawdown_pct": round(drawdown_pct, 4),
            "drawdown_kill_pct": drawdown_kill_pct,
            "mc_drawdown_pct": mc_drawdown_pct,
            "consecutive_losses": consecutive_losses,
            "pending_reconciliations": len(getattr(app, "pending_trade_reconciliations", []) or []),
            "last_trades": list(getattr(app, "trade_log", []) or [])[-10:],
            "equity_curve": equity_curve,
            "pnl_history": pnl_history,
            "session_kpis": session_kpis,
        }
        write_runtime_monitoring_snapshot(payload)
