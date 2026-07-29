"""PDF / chart / JSON report helpers mixed into PerformanceValidator."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
import requests

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fpdf import FPDF

from lumina_core.evolution.simulator_data_support import coerce_rl_training_bars


class PerformanceValidatorPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "LUMINA Performance Validator Report", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


class PerformanceValidatorReportMixin:
    """Chart, monthly PDF, JSON persistence, and emergency report actions."""

    __slots__ = ()

    def _persist_summary(self, summary: dict[str, Any]) -> str:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self.report_dir / f"validator_3y_swarm_{ts}.json"
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return str(out_path)

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
            if self.market_data_service is None:
                raise RuntimeError("market_data_service missing for emergency retrain")
            if self.ppo_trainer is None:
                raise RuntimeError("ppo_trainer missing for emergency retrain")

            simulator_data = self.market_data_service.load_historical_ohlc_extended(days_back=365, limit=120000)
            if hasattr(self.ppo_trainer, "train_nightly_on_infinite_simulator"):
                policy_path = self.ppo_trainer.train_nightly_on_infinite_simulator(simulator_data, timesteps=300_000)
            else:
                eng = getattr(self.ppo_trainer, "engine", None)
                if eng is None:
                    raise RuntimeError("ppo_trainer.engine missing for emergency RL retrain")
                bars = coerce_rl_training_bars(
                    eng, simulator_data if isinstance(simulator_data, list) else None, nightly_context=None
                )
                policy_path = self.ppo_trainer.train(bars, total_timesteps=300_000)
            actions["rl_retrain"] = True
            actions["rl_policy_path"] = str(policy_path)
        except Exception as exc:
            app.logger.error(f"Emergency RL retrain failed: {exc}")

        alert = self._send_emergency_alert(reason=reason, actions=actions)
        actions["alert_sent"] = bool(alert.get("sent", False))
        actions["alert_target"] = str(alert.get("target", "logger"))

        app.log_thought({"type": "validator_emergency_action", "actions": actions})
        return actions

    def _send_emergency_alert(self, reason: str, actions: dict[str, Any]) -> dict[str, Any]:
        app = self._app()
        payload = {
            "type": "validator_emergency",
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "actions": actions,
        }

        app.logger.critical(f"VALIDATOR_EMERGENCY_TRIGGERED: {reason}")
        app.log_thought(payload)

        webhook_url = os.getenv("VALIDATOR_ALERT_WEBHOOK_URL", "").strip()
        if not webhook_url:
            return {"sent": False, "target": "logger"}

        try:
            response = requests.post(webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            return {"sent": True, "target": webhook_url}
        except Exception as exc:
            app.logger.error(f"Validator emergency webhook failed: {exc}")
            return {"sent": False, "target": webhook_url}

    def _save_report_chart(self, validator_summary: dict[str, Any], side: dict[str, Any]) -> str | None:
        symbols = list(validator_summary.get("symbols", []))
        if not symbols:
            return None

        try:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            chart_path = self.report_dir / f"LUMINA_Validation_{datetime.now().strftime('%Y%m')}_chart.png"

            symbol_names = [str(item.get("symbol", "?")) for item in symbols]
            monthly_returns = [float(item.get("monthly_return", 0.0)) * 100.0 for item in symbols]
            maxdds = [float(item.get("worst_maxdd_all_tests", 0.0)) for item in symbols]
            paper_curve = list(side.get("paper_curve", []))
            real_curve = list(side.get("real_curve", []))

            fig, axes = plt.subplots(2, 2, figsize=(12, 8))

            axes[0, 0].bar(symbol_names, monthly_returns, color="#1f77b4")
            axes[0, 0].axhline(
                self._goal_targets()["min_monthly_return"] * 100.0, color="green", linestyle="--", linewidth=1
            )
            axes[0, 0].axhline(
                self._goal_targets()["max_monthly_return"] * 100.0, color="green", linestyle="--", linewidth=1
            )
            axes[0, 0].set_title("Monthly Return by Symbol (%)")
            axes[0, 0].tick_params(axis="x", rotation=30)

            axes[0, 1].bar(symbol_names, maxdds, color="#d62728")
            axes[0, 1].axhline(self._goal_targets()["max_maxdd"], color="black", linestyle="--", linewidth=1)
            axes[0, 1].set_title("Worst Max Drawdown by Symbol (%)")
            axes[0, 1].tick_params(axis="x", rotation=30)

            axes[1, 0].plot(paper_curve, label="paper", color="#2ca02c")
            axes[1, 0].plot(real_curve, label="real", color="#9467bd")
            axes[1, 0].set_title("Paper vs Real Equity (aligned)")
            axes[1, 0].legend()

            corr = float(side.get("correlation", 0.0))
            axes[1, 1].axis("off")
            axes[1, 1].text(
                0.0,
                0.9,
                (
                    f"Correlation: {corr:.3f}\n"
                    f"Paper Sharpe: {float(side.get('paper_sharpe', 0.0)):.2f}\n"
                    f"Real Sharpe: {float(side.get('real_sharpe', 0.0)):.2f}\n"
                    f"Divergence Alert: {bool(side.get('divergence_alert', False))}"
                ),
                fontsize=11,
                va="top",
            )

            plt.tight_layout()
            fig.savefig(chart_path, dpi=150)
            plt.close(fig)
            return str(chart_path)
        except Exception as exc:
            self._app().logger.error(f"Validator chart generation failed: {exc}")
            return None

    def generate_monthly_report_pdf(self, validator_summary: dict[str, Any] | None = None) -> str | None:
        # Backward-compatible alias retained for existing call sites.
        return self._generate_monthly_pdf(validator_summary)

    def _generate_monthly_pdf(self, validator_summary: dict[str, Any] | None = None) -> str | None:
        app = self._app()
        try:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            if validator_summary is None:
                validator_summary = self.run_full_swarm_validation_3y()

            side = dict(validator_summary.get("side_by_side") or self.live_paper_vs_real_comparison(max_points=200))
            agg = dict(validator_summary.get("aggregate", {}))
            goals = dict(validator_summary.get("goals", {}))
            chart_path = self._save_report_chart(validator_summary, side)
            monthly_return_pct = float(agg.get("mean_monthly_return", 0.0)) * 100.0

            pdf = PerformanceValidatorPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(
                0, 8, f"Monthly Validation Report - {datetime.now().strftime('%Y-%m')}", new_x="LMARGIN", new_y="NEXT"
            )
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(0, 7, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 7, f"Goal met: {bool(validator_summary.get('goal_met', False))}", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(
                0,
                7,
                (
                    f"Aggregate -> Mean Monthly {monthly_return_pct:.2f}% | "
                    f"Worst MaxDD {float(agg.get('worst_maxdd', 0.0)):.2f}% | "
                    f"Mean Sharpe {float(agg.get('mean_sharpe', 0.0)):.2f} | Trades {int(agg.get('trades', 0))}"
                ),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.cell(
                0,
                7,
                (
                    f"Goals -> Monthly {float(goals.get('min_monthly_return', 0.0)) * 100.0:.1f}% to "
                    f"{float(goals.get('max_monthly_return', 0.0)) * 100.0:.1f}% | "
                    f"MaxDD <= {float(goals.get('max_maxdd', 0.0)):.2f}% | "
                    f"Paper/Real Corr >= {float(goals.get('min_paper_real_corr', 0.0)):.2f}"
                ),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.ln(4)

            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(0, 7, "Live Paper vs Real Snapshot", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(
                0,
                6,
                (
                    f"Paper last equity: {float(side.get('paper_equity_last', 0.0)):.2f}, "
                    f"Paper Sharpe: {float(side.get('paper_sharpe', 0.0)):.2f}, points: {int(side.get('paper_points', 0))}\n"
                    f"Real last equity: {float(side.get('real_equity_last', 0.0)):.2f}, "
                    f"Real Sharpe: {float(side.get('real_sharpe', 0.0)):.2f}, points: {int(side.get('real_points', 0))}\n"
                    f"Correlation: {float(side.get('correlation', 0.0)):.3f}, Divergence alert: {bool(side.get('divergence_alert', False))}"
                ),
            )
            pdf.ln(2)

            if chart_path and Path(chart_path).exists():
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 7, "Validation Charts", new_x="LMARGIN", new_y="NEXT")
                img_y = pdf.get_y()
                page_width = 210 - 20  # A4 width minus margins
                pdf.image(chart_path, x=10, y=img_y, w=page_width)
                pdf.ln(90)
                pdf.set_x(pdf.l_margin)

            pdf.set_font("Helvetica", "B", 11)
            pdf.set_x(pdf.l_margin)
            pdf.cell(0, 7, "Per-Symbol Results (3Y swarm)", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            for row in validator_summary.get("symbols", []):
                if not isinstance(row, dict):
                    continue
                pdf.set_x(pdf.l_margin)
                pdf.multi_cell(
                    0,
                    6,
                    (
                        f"{row.get('symbol', '?')}: Monthly {float(row.get('monthly_return', 0.0)) * 100.0:.2f}%, "
                        f"Sharpe {float(row.get('sharpe', 0)):.2f}, Winrate {float(row.get('winrate', 0)):.1%}, "
                        f"Worst MaxDD {float(row.get('worst_maxdd_all_tests', 0.0)):.2f}%, "
                        f"Net {float(row.get('net_pnl', 0)):.2f}, Trades {int(row.get('trades', 0))}"
                    ),
                )

            out_path = self.report_dir / f"LUMINA_Validation_{datetime.now().strftime('%Y%m')}.pdf"
            pdf.output(str(out_path))
            app.logger.info(f"Monthly validation PDF generated: {out_path}")
            return str(out_path)
        except Exception as exc:
            app.logger.error(f"Monthly validator report error: {exc}")
            return None


__all__ = ["PerformanceValidatorPDF", "PerformanceValidatorReportMixin"]
