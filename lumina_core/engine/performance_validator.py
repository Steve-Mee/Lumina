from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from fpdf import FPDF

from lumina_core.backtester_engine import BacktesterEngine
from .lumina_engine import LuminaEngine
from .market_data_service import MarketDataService


class PerformanceValidatorPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "LUMINA Performance Validator Report", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


@dataclass(slots=True)
class PerformanceValidator:
    engine: LuminaEngine
    market_data_service: MarketDataService | None = None
    ppo_trainer: Any | None = None
    report_dir: Path = Path("journal/reports")
    side_by_side_log: list[dict[str, Any]] = field(default_factory=list)
    real_audit_path: Path = Path("logs/trade_fill_audit.jsonl")
    monte_carlo_runs: int = 500
    initial_equity: float = 50000.0

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("PerformanceValidator requires LuminaEngine")
        if self.market_data_service is None:
            self.market_data_service = MarketDataService(engine=self.engine)
        if self.ppo_trainer is None:
            self.ppo_trainer = getattr(self.engine, "ppo_trainer", None)

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    @staticmethod
    def _goal_targets() -> dict[str, float]:
        return {
            "min_monthly_return": float(os.getenv("VALIDATOR_MIN_MONTHLY_RETURN", "0.05")),
            "max_monthly_return": float(os.getenv("VALIDATOR_MAX_MONTHLY_RETURN", "0.10")),
            "max_maxdd": float(os.getenv("VALIDATOR_MAX_MAXDD", "8.0")),
            "min_paper_real_corr": float(os.getenv("VALIDATOR_MIN_PAPER_REAL_CORR", "0.85")),
        }

    def _persist_summary(self, summary: dict[str, Any]) -> str:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = self.report_dir / f"validator_3y_swarm_{ts}.json"
        out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return str(out_path)

    @staticmethod
    def _safe_pct_change(values: list[float]) -> list[float]:
        if len(values) < 2:
            return []
        out: list[float] = []
        for i in range(1, len(values)):
            prev = float(values[i - 1])
            curr = float(values[i])
            if prev <= 0:
                continue
            out.append((curr - prev) / prev)
        return out

    @staticmethod
    def _annualized_sharpe_from_equity(values: list[float], periods_per_year: float = 252.0) -> float:
        returns = PerformanceValidator._safe_pct_change(values)
        if len(returns) < 2:
            return 0.0
        mean_r = float(np.mean(returns))
        std_r = float(np.std(returns, ddof=1))
        if std_r <= 1e-12:
            return 0.0
        return (mean_r / std_r) * math.sqrt(periods_per_year)

    @staticmethod
    def _normalize_to_common_length(values: list[float], target_len: int) -> list[float]:
        if target_len <= 0:
            return []
        if not values:
            return [0.0] * target_len
        if len(values) == target_len:
            return [float(x) for x in values]
        x_old = np.linspace(0.0, 1.0, len(values))
        x_new = np.linspace(0.0, 1.0, target_len)
        y = np.interp(x_new, x_old, np.array(values, dtype=np.float64))
        return [float(v) for v in y]

    def _extract_real_equity_curve(self, max_points: int = 200) -> list[float]:
        if not self.real_audit_path.exists():
            return []

        events: list[dict[str, Any]] = []
        try:
            for line in self.real_audit_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                if str(payload.get("event", "")).lower() != "reconciled":
                    continue
                pnl = float(payload.get("pnl", 0.0) or 0.0)
                ts = str(payload.get("ts", "") or "")
                events.append({"ts": ts, "pnl": pnl})
        except Exception as exc:
            self._app().logger.error(f"Real equity curve parse failed: {exc}")
            return []

        if not events:
            return []

        events.sort(key=lambda item: item.get("ts", ""))
        start = float(self.initial_equity)
        paper_curve = getattr(self.engine, "equity_curve", []) or []
        if paper_curve:
            start = float(paper_curve[0])

        curve = [start]
        running = start
        for event in events:
            running += float(event["pnl"])
            curve.append(float(running))
        return curve[-max_points:]

    def capture_live_side_by_side_snapshot(self) -> dict[str, Any]:
        side = self.live_paper_vs_real_comparison(max_points=200)
        row = {
            "ts": datetime.now().isoformat(),
            "paper": {
                "equity": float(side.get("paper_equity_last", 0.0)),
                "sharpe": float(side.get("paper_sharpe", 0.0)),
                "points": int(side.get("paper_points", 0)),
            },
            "real": {
                "equity": float(side.get("real_equity_last", 0.0)),
                "sharpe": float(side.get("real_sharpe", 0.0)),
                "points": int(side.get("real_points", 0)),
            },
            "correlation": float(side.get("correlation", 0.0)),
            "divergence_alert": bool(side.get("divergence_alert", False)),
        }

        app = self._app()
        self.side_by_side_log.append(row)
        if len(self.side_by_side_log) > 2000:
            self.side_by_side_log = self.side_by_side_log[-2000:]
        app.log_thought({"type": "validator_side_by_side", "snapshot": row})
        return row

    def _load_swarm_symbol_snapshot(self, symbol: str) -> pd.DataFrame:
        market_data_service = self.market_data_service
        if market_data_service is None:
            raise RuntimeError("PerformanceValidator.market_data_service is not configured")

        df = market_data_service.load_historical_ohlc_for_symbol(
            instrument=symbol,
            days_back=365 * 3,
            limit=300000,
        )
        if df.empty:
            return df
        if "timestamp" in df.columns:
            df = df.copy()
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"])
            df = df.sort_values("timestamp")
        return df

    def _validate_symbol_snapshot(self, symbol: str, df: pd.DataFrame) -> dict[str, Any]:
        bt = BacktesterEngine(app=cast(Any, self._app()))
        snapshot = [{str(k): v for k, v in row.items()} for row in df.to_dict("records")]
        base_report = bt.run_snapshot_backtest(snapshot)

        advanced = getattr(self.engine, "advanced_backtester", None)
        walk_forward = {}
        monte_advanced = {}
        if advanced is not None:
            try:
                walk_forward = dict(advanced.walk_forward_test(df.copy()))
            except Exception as exc:
                self._app().logger.error(f"Walk-forward failed for {symbol}: {exc}")
            try:
                monte_advanced = dict(advanced.full_monte_carlo(df.copy(), runs=int(self.monte_carlo_runs)))
            except Exception as exc:
                self._app().logger.error(f"Advanced Monte-Carlo failed for {symbol}: {exc}")

        net_pnl = float(base_report.get("net_pnl", 0.0))
        monthly_return = (net_pnl / float(self.initial_equity)) / 36.0
        worst_maxdd_candidates = [
            float(base_report.get("maxdd", 0.0)),
            float(walk_forward.get("worst_test_maxdd", 0.0)),
            float(monte_advanced.get("worst_maxdd", 0.0)),
        ]

        return {
            "symbol": symbol,
            "bars": int(len(df)),
            "trades": int(base_report.get("trades", 0)),
            "net_pnl": net_pnl,
            "sharpe": float(base_report.get("sharpe", 0.0)),
            "winrate": float(base_report.get("winrate", 0.0)),
            "maxdd": float(base_report.get("maxdd", 0.0)),
            "monthly_return": float(monthly_return),
            "monte_carlo": dict(base_report.get("monte_carlo", {})),
            "walk_forward": dict(base_report.get("walk_forward", {})),
            "walk_forward_optimization": dict(base_report.get("walk_forward_optimization", {})),
            "advanced_walk_forward": walk_forward,
            "advanced_monte_carlo": monte_advanced,
            "worst_maxdd_all_tests": float(max(worst_maxdd_candidates)),
        }

    def run_full_swarm_validation_3y(self) -> dict[str, Any]:
        app = self._app()
        if self.market_data_service is None:
            raise RuntimeError("PerformanceValidator.market_data_service is not configured")
        symbols = [
            str(s).strip().upper()
            for s in getattr(app, "SWARM_SYMBOLS", [self.engine.config.instrument])
            if str(s).strip()
        ]
        results: list[dict[str, Any]] = []

        for symbol in symbols:
            try:
                df = self._load_swarm_symbol_snapshot(symbol)
                if df.empty:
                    continue
                results.append(self._validate_symbol_snapshot(symbol, df))
            except Exception as exc:
                app.logger.error(f"Validator error for {symbol}: {exc}")

        goals = self._goal_targets()
        side_by_side = self.live_paper_vs_real_comparison(max_points=200)

        if not results:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "symbols": [],
                "aggregate": {
                    "mean_monthly_return": 0.0,
                    "median_monthly_return": 0.0,
                    "consistency_ratio": 0.0,
                    "worst_maxdd": 100.0,
                    "mean_sharpe": 0.0,
                    "mean_winrate": 0.0,
                    "net_pnl": 0.0,
                    "trades": 0,
                },
                "side_by_side": side_by_side,
                "goals": goals,
                "goal_met": False,
                "reason": "No historical swarm data",
            }
            summary["json_path"] = self._persist_summary(summary)
            self._generate_monthly_pdf(summary)
            return summary

        monthly_returns = [float(x["monthly_return"]) for x in results]
        per_symbol_worst_dd = [float(x["worst_maxdd_all_tests"]) for x in results]
        consistency_hits = [goals["min_monthly_return"] <= m <= goals["max_monthly_return"] for m in monthly_returns]

        agg = {
            "mean_monthly_return": float(np.mean(monthly_returns)),
            "median_monthly_return": float(np.median(monthly_returns)),
            "consistency_ratio": float(np.mean(consistency_hits)),
            "worst_maxdd": float(max(per_symbol_worst_dd)),
            "mean_sharpe": float(np.mean([x["sharpe"] for x in results])),
            "mean_winrate": float(np.mean([x["winrate"] for x in results])),
            "net_pnl": sum(x["net_pnl"] for x in results),
            "trades": int(sum(x["trades"] for x in results)),
        }

        goal_met = (
            goals["min_monthly_return"] <= agg["mean_monthly_return"] <= goals["max_monthly_return"]
            and agg["worst_maxdd"] <= goals["max_maxdd"]
            and bool(side_by_side.get("correlation", 0.0) >= goals["min_paper_real_corr"])
        )

        summary = {
            "timestamp": datetime.now().isoformat(),
            "symbols": results,
            "aggregate": agg,
            "side_by_side": side_by_side,
            "goals": goals,
            "goal_met": bool(goal_met),
        }

        summary["json_path"] = self._persist_summary(summary)
        summary["monthly_pdf"] = self._generate_monthly_pdf(summary)

        app.log_thought({"type": "validator_3y_swarm", "summary": summary})
        return summary

    def run_3year_validation(self) -> dict[str, Any]:
        summary = self.run_full_swarm_validation_3y()
        aggregate = dict(summary.get("aggregate", {}))
        return {
            "status": "goal_met" if bool(summary.get("goal_met", False)) else "goal_missed",
            "mean_monthly_return": round(float(aggregate.get("mean_monthly_return", 0.0)) * 100.0, 2),
            "worst_maxdd": round(float(aggregate.get("worst_maxdd", 0.0)), 2),
            "mean_sharpe": round(float(aggregate.get("mean_sharpe", 0.0)), 2),
            "mean_winrate": round(float(aggregate.get("mean_winrate", 0.0)), 3),
            "consistency_ratio": round(float(aggregate.get("consistency_ratio", 0.0)), 3),
            "side_by_side_correlation": round(float(summary.get("side_by_side", {}).get("correlation", 0.0)), 3),
            "num_symbols": len(summary.get("symbols", [])),
            "goal_met": bool(summary.get("goal_met", False)),
            "json_path": summary.get("json_path"),
            "monthly_pdf": summary.get("monthly_pdf"),
        }

    def live_paper_vs_real_comparison(self, max_points: int = 200) -> dict[str, Any]:
        paper_curve = [float(x) for x in (getattr(self.engine, "equity_curve", []) or [])][-max_points:]
        if not paper_curve:
            paper_curve = [float(getattr(self.engine, "account_equity", self.initial_equity))]

        real_curve = self._extract_real_equity_curve(max_points=max_points)
        if not real_curve:
            real_curve = [float(getattr(self.engine, "account_equity", paper_curve[-1]))]

        n = max(2, min(max_points, max(len(paper_curve), len(real_curve))))
        paper_aligned = self._normalize_to_common_length(paper_curve, n)
        real_aligned = self._normalize_to_common_length(real_curve, n)

        correlation = 0.0
        if len(paper_aligned) > 1 and len(real_aligned) > 1:
            pstd = float(np.std(paper_aligned))
            rstd = float(np.std(real_aligned))
            if pstd > 1e-12 and rstd > 1e-12:
                correlation = float(np.corrcoef(np.array(paper_aligned), np.array(real_aligned))[0, 1])

        paper_sharpe = self._annualized_sharpe_from_equity(paper_aligned)
        real_sharpe = self._annualized_sharpe_from_equity(real_aligned)
        divergence_alert = bool(correlation < self._goal_targets()["min_paper_real_corr"])

        return {
            "paper_sharpe": float(paper_sharpe),
            "real_sharpe": float(real_sharpe),
            "correlation": round(float(correlation), 3),
            "divergence_alert": divergence_alert,
            "paper_points": int(len(paper_curve)),
            "real_points": int(len(real_curve)),
            "paper_equity_last": float(paper_curve[-1]),
            "real_equity_last": float(real_curve[-1]),
            "paper_curve": paper_aligned,
            "real_curve": real_aligned,
        }

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
                self.ppo_trainer.train(total_timesteps=300_000)
                policy_path = ""
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

    def run_validation_cycle(self) -> dict[str, Any]:
        summary = self.run_full_swarm_validation_3y()
        summary["monthly_pdf"] = summary.get("monthly_pdf") or self._generate_monthly_pdf(summary)

        if not bool(summary.get("goal_met", False)):
            reason = (
                f"Goal not met: monthly={float(summary.get('aggregate', {}).get('mean_monthly_return', 0.0)) * 100.0:.2f}%, "
                f"worst_maxdd={float(summary.get('aggregate', {}).get('worst_maxdd', 0.0)):.2f}%, "
                f"paper_real_corr={float(summary.get('side_by_side', {}).get('correlation', 0.0)):.3f}"
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
                        self.side_by_side_log.append(
                            {"monthly_marker": marker, "result_path": result.get("json_path", "")}
                        )
                        app.log_thought({"type": "monthly_validator_cycle", "result": result})
                else:
                    # Keep side-by-side tracking alive even outside monthly runs.
                    self.capture_live_side_by_side_snapshot()
            except Exception as exc:
                app.logger.error(f"Performance validator daemon error: {exc}")

            time.sleep(3600)
