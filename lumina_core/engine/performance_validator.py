from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF

from lumina_core.backtester_engine import BacktesterEngine
from .lumina_engine import LuminaEngine
from .market_data_service import MarketDataService


class PerformanceValidatorPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, "LUMINA Performance Validator Report", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


@dataclass(slots=True)
class PerformanceValidator:
    engine: LuminaEngine
    market_data_service: MarketDataService
    ppo_trainer: Any
    report_dir: Path = Path("journal/performance_validator")
    side_by_side_log: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("PerformanceValidator requires LuminaEngine")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    @staticmethod
    def _goal_targets() -> dict[str, float]:
        import os

        return {
            "min_sharpe": float(os.getenv("VALIDATOR_MIN_SHARPE", "1.2")),
            "min_winrate": float(os.getenv("VALIDATOR_MIN_WINRATE", "0.55")),
            "max_maxdd": float(os.getenv("VALIDATOR_MAX_MAXDD", "15.0")),
        }

    def capture_live_side_by_side_snapshot(self) -> dict[str, Any]:
        app = self._app()
        ts = datetime.now().isoformat()

        paper_snapshot = {
            "mode": "paper",
            "equity": float(self.engine.equity_curve[-1]) if self.engine.equity_curve else float(self.engine.account_equity),
            "open_pnl": float(self.engine.open_pnl),
            "realized_pnl_today": float(self.engine.realized_pnl_today),
            "trades": int(len(self.engine.trade_log)),
        }
        real_snapshot = {
            "mode": "real",
            "account_equity": float(self.engine.account_equity),
            "account_balance": float(self.engine.account_balance),
            "open_pnl": float(self.engine.open_pnl),
            "realized_pnl_today": float(self.engine.realized_pnl_today),
        }

        row = {"ts": ts, "paper": paper_snapshot, "real": real_snapshot}
        self.side_by_side_log.append(row)
        if len(self.side_by_side_log) > 2000:
            self.side_by_side_log = self.side_by_side_log[-2000:]

        app.log_thought({"type": "validator_side_by_side", "snapshot": row})
        return row

    def _validate_symbol_snapshot(self, symbol: str, snapshot: list[dict[str, Any]]) -> dict[str, Any]:
        bt = BacktesterEngine(app=self._app())
        report = bt.run_snapshot_backtest(snapshot)
        return {
            "symbol": symbol,
            "trades": int(report.get("trades", 0)),
            "sharpe": float(report.get("sharpe", 0.0)),
            "winrate": float(report.get("winrate", 0.0)),
            "maxdd": float(report.get("maxdd", 0.0)),
            "net_pnl": float(report.get("net_pnl", 0.0)),
            "monte_carlo": dict(report.get("monte_carlo", {})),
            "walk_forward": dict(report.get("walk_forward", {})),
            "walk_forward_optimization": dict(report.get("walk_forward_optimization", {})),
        }

    def run_full_swarm_validation_3y(self) -> dict[str, Any]:
        app = self._app()
        symbols = [str(s).strip().upper() for s in getattr(app, "SWARM_SYMBOLS", [self.engine.config.instrument]) if str(s).strip()]
        results: list[dict[str, Any]] = []

        for symbol in symbols:
            try:
                # 3-year equivalent window.
                df = self.market_data_service.load_historical_ohlc_for_symbol(
                    instrument=symbol,
                    days_back=365 * 3,
                    limit=300000,
                )
                if df.empty:
                    continue
                snapshot = df.to_dict("records")
                results.append(self._validate_symbol_snapshot(symbol, snapshot))
            except Exception as exc:
                app.logger.error(f"Validator error for {symbol}: {exc}")

        if not results:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "symbols": [],
                "aggregate": {"sharpe": 0.0, "winrate": 0.0, "maxdd": 100.0, "net_pnl": 0.0, "trades": 0},
                "goals": self._goal_targets(),
                "goal_met": False,
                "reason": "No historical swarm data",
            }
            return summary

        agg = {
            "sharpe": sum(x["sharpe"] for x in results) / max(1, len(results)),
            "winrate": sum(x["winrate"] for x in results) / max(1, len(results)),
            "maxdd": max(x["maxdd"] for x in results),
            "net_pnl": sum(x["net_pnl"] for x in results),
            "trades": int(sum(x["trades"] for x in results)),
        }
        goals = self._goal_targets()
        goal_met = (
            agg["sharpe"] >= goals["min_sharpe"]
            and agg["winrate"] >= goals["min_winrate"]
            and agg["maxdd"] <= goals["max_maxdd"]
        )

        summary = {
            "timestamp": datetime.now().isoformat(),
            "symbols": results,
            "aggregate": agg,
            "goals": goals,
            "goal_met": bool(goal_met),
        }

        self.report_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.report_dir / f"validator_3y_swarm_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["json_path"] = str(json_path)

        app.log_thought({"type": "validator_3y_swarm", "summary": summary})
        return summary

    def emergency_dna_rewrite_and_rl_retrain(self, reason: str) -> dict[str, Any]:
        app = self._app()
        actions: dict[str, Any] = {"reason": reason, "dna_rewrite": False, "rl_retrain": False, "rl_policy_path": ""}

        try:
            app.process_user_feedback(
                f"EMERGENCY VALIDATOR TRIGGER: {reason}. Force immediate bible/evolvable_layer hardening.",
                {"signal": "VALIDATOR", "pnl": 0},
            )
            actions["dna_rewrite"] = True
        except Exception as exc:
            app.logger.error(f"Emergency DNA rewrite trigger failed: {exc}")

        try:
            simulator_data = self.market_data_service.load_historical_ohlc_extended(days_back=365, limit=120000)
            policy_path = self.ppo_trainer.train_nightly_on_infinite_simulator(simulator_data, timesteps=300_000)
            actions["rl_retrain"] = True
            actions["rl_policy_path"] = str(policy_path)
        except Exception as exc:
            app.logger.error(f"Emergency RL retrain failed: {exc}")

        app.log_thought({"type": "validator_emergency_action", "actions": actions})
        return actions

    def generate_monthly_report_pdf(self, validator_summary: dict[str, Any] | None = None) -> str | None:
        app = self._app()
        try:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            if validator_summary is None:
                validator_summary = self.run_full_swarm_validation_3y()

            side = self.capture_live_side_by_side_snapshot()
            agg = dict(validator_summary.get("aggregate", {}))
            goals = dict(validator_summary.get("goals", {}))

            pdf = PerformanceValidatorPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 8, f"Monthly Validation Report - {datetime.now().strftime('%Y-%m')}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Arial", "", 11)
            pdf.cell(0, 7, f"Goal met: {validator_summary.get('goal_met', False)}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(
                0,
                7,
                f"Aggregate -> Sharpe {agg.get('sharpe', 0):.2f} | Winrate {agg.get('winrate', 0):.1%} | MaxDD {agg.get('maxdd', 0):.2f}% | Trades {agg.get('trades', 0)}",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.cell(
                0,
                7,
                f"Goals -> Sharpe >= {goals.get('min_sharpe', 0)} | Winrate >= {goals.get('min_winrate', 0):.1%} | MaxDD <= {goals.get('max_maxdd', 0):.2f}%",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.ln(4)

            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 7, "Live Paper vs Real Snapshot", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(
                0,
                6,
                (
                    f"TS: {side.get('ts')}\n"
                    f"Paper -> equity {side.get('paper', {}).get('equity', 0):.2f}, open {side.get('paper', {}).get('open_pnl', 0):.2f}, realized {side.get('paper', {}).get('realized_pnl_today', 0):.2f}\n"
                    f"Real  -> equity {side.get('real', {}).get('account_equity', 0):.2f}, open {side.get('real', {}).get('open_pnl', 0):.2f}, realized {side.get('real', {}).get('realized_pnl_today', 0):.2f}"
                ),
            )
            pdf.ln(2)

            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 7, "Per-Symbol Results (3Y swarm)", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Arial", "", 10)
            for row in validator_summary.get("symbols", []):
                if not isinstance(row, dict):
                    continue
                pdf.multi_cell(
                    0,
                    6,
                    (
                        f"{row.get('symbol','?')}: Sharpe {float(row.get('sharpe', 0)):.2f}, "
                        f"Winrate {float(row.get('winrate', 0)):.1%}, MaxDD {float(row.get('maxdd', 0)):.2f}%, "
                        f"Net {float(row.get('net_pnl', 0)):.2f}, Trades {int(row.get('trades', 0))}"
                    ),
                )

            out_path = self.report_dir / f"monthly_validator_report_{datetime.now().strftime('%Y%m')}.pdf"
            pdf.output(str(out_path))
            return str(out_path)
        except Exception as exc:
            app.logger.error(f"Monthly validator report error: {exc}")
            return None

    def run_validation_cycle(self) -> dict[str, Any]:
        summary = self.run_full_swarm_validation_3y()
        report_path = self.generate_monthly_report_pdf(summary)
        summary["monthly_pdf"] = report_path

        if not bool(summary.get("goal_met", False)):
            reason = (
                f"Goal not met: Sharpe {summary.get('aggregate', {}).get('sharpe', 0):.2f}, "
                f"Winrate {summary.get('aggregate', {}).get('winrate', 0):.1%}, "
                f"MaxDD {summary.get('aggregate', {}).get('maxdd', 0):.2f}%"
            )
            summary["emergency_actions"] = self.emergency_dna_rewrite_and_rl_retrain(reason)
        else:
            summary["emergency_actions"] = {"triggered": False}

        return summary

    def monthly_validation_daemon(self) -> None:
        app = self._app()
        while True:
            try:
                now = datetime.now()
                # Run once on first day between 00:00-01:00 local time.
                if now.day == 1 and now.hour == 0:
                    marker = f"{now.year:04d}-{now.month:02d}"
                    existing = [x for x in self.side_by_side_log if str(x.get("monthly_marker", "")) == marker]
                    if not existing:
                        result = self.run_validation_cycle()
                        self.side_by_side_log.append({"monthly_marker": marker, "result_path": result.get("json_path", "")})
                        app.log_thought({"type": "monthly_validator_cycle", "result": result})
                else:
                    # Keep side-by-side tracking alive even outside monthly runs.
                    self.capture_live_side_by_side_snapshot()
            except Exception as exc:
                app.logger.error(f"Performance validator daemon error: {exc}")

            time.sleep(3600)
