"""PerformanceValidator façade — swarm validation + live paper/real comparison.

Bounded module: ``performance_validator_report`` (PDF / chart / PerformanceValidatorPDF).
Public symbols remain importable from this module.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

from lumina_core.engine.canonical_training import BacktesterEngine
from .lumina_engine import LuminaEngine
from .market_data_service import MarketDataIngestService
from .performance_validator_report import PerformanceValidatorPDF, PerformanceValidatorReportMixin

__all__ = ["PerformanceValidator", "PerformanceValidatorPDF"]


@dataclass(slots=True)
class PerformanceValidator(PerformanceValidatorReportMixin):
    engine: LuminaEngine
    market_data_service: MarketDataIngestService | None = None
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
            self.market_data_service = MarketDataIngestService(engine=self.engine)
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
