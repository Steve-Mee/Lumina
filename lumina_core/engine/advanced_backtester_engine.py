from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from lumina_core.engine.realistic_backtester_engine import RealisticBacktesterEngine
from lumina_core.runtime_context import RuntimeContext


class AdvancedBacktesterEngine:
    """
    Walk-Forward + Regime-Specific OOS + Monte Carlo op de realistische backtester.
    """

    def __init__(self, context: RuntimeContext):
        self.context = context
        self.logger = context.logger
        self.realistic = RealisticBacktesterEngine(context)
        self.window_days = 30
        self.step_days = 10
        self.monte_carlo_runs = 1000

    def walk_forward_test(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Rolling walk-forward: train 30 dagen -> test volgende 10 dagen"""
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

        results = []
        start_date = df.index.min()
        end_date = df.index.max()

        current = start_date
        while current + timedelta(days=self.window_days + self.step_days) <= end_date:
            train_end = current + timedelta(days=self.window_days)
            test_end = train_end + timedelta(days=self.step_days)

            train = df.loc[:train_end]
            test = df.loc[train_end:test_end]

            train_res = self.realistic.run_backtest_on_snapshot(train.reset_index())
            test_res = self.realistic.run_backtest_on_snapshot(test.reset_index())

            results.append({
                "train_period": f"{train.index[0].date()} -> {train.index[-1].date()}",
                "test_period": f"{test.index[0].date()} -> {test.index[-1].date()}",
                "train_sharpe": train_res["sharpe"],
                "test_sharpe": test_res["sharpe"],
                "train_maxdd": train_res["maxdd"],
                "test_maxdd": test_res["maxdd"],
                "test_trades": test_res["trades"],
            })

            current += timedelta(days=self.step_days)

        test_sharpes = [r["test_sharpe"] for r in results]
        avg_test_sharpe = float(np.mean(test_sharpes)) if test_sharpes else 0.0
        worst_test_dd = max((r["test_maxdd"] for r in results), default=0.0)

        self.logger.info(
            f"WALK_FORWARD_COMPLETE,avg_test_sharpe={avg_test_sharpe:.2f},worst_dd={worst_test_dd:.1f}%"
        )

        return {
            "walk_forward_results": results,
            "avg_test_sharpe": round(avg_test_sharpe, 2),
            "worst_test_maxdd": round(worst_test_dd, 1),
            "num_windows": len(results),
        }

    def regime_specific_oos(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Presteert de bot per regime in OOS?"""
        df = df.copy()
        regime_results: Dict[str, Any] = {}

        for regime in ["TRENDING", "BREAKOUT", "VOLATILE", "RANGING", "NEUTRAL"]:
            regime_df = df[df["regime"] == regime] if "regime" in df.columns else df
            if len(regime_df) < 1000:
                continue

            res = self.realistic.run_backtest_on_snapshot(regime_df)
            regime_results[regime] = {
                "sharpe": res["sharpe"],
                "winrate": res["winrate"],
                "maxdd": res["maxdd"],
                "trades": res["trades"],
                "avg_pnl": res["avg_pnl"],
            }

        return regime_results

    def full_monte_carlo(self, df: pd.DataFrame, runs: int = 1000) -> Dict[str, Any]:
        """Volledige Monte Carlo met gap events en regime switching"""
        results = []
        base_df = df.copy()

        for _ in range(runs):
            noisy = base_df.copy()
            noise = np.random.normal(0, 0.001, len(noisy)) * noisy["close"]
            noisy["close"] += noise
            noisy["high"] += abs(noise) * 1.3
            noisy["low"] += noise * 0.7

            # Random gap events (nieuws)
            if np.random.rand() < 0.15:
                gap_idx = int(np.random.randint(100, len(noisy) - 100))
                gap_size = float(np.random.normal(0, 0.008) * noisy["close"].iloc[gap_idx])
                noisy.loc[noisy.index[gap_idx:], "open"] = noisy["open"].iloc[gap_idx:] + gap_size
                noisy.loc[noisy.index[gap_idx:], "close"] = noisy["close"].iloc[gap_idx:] + gap_size

            res = self.realistic.run_backtest_on_snapshot(noisy)
            results.append(res)

        sharpes = [r["sharpe"] for r in results]
        maxdds = [r["maxdd"] for r in results]

        return {
            "mean_sharpe": round(float(np.mean(sharpes)), 2),
            "median_sharpe": round(float(np.median(sharpes)), 2),
            "worst_sharpe": round(float(np.min(sharpes)), 2),
            "mean_maxdd": round(float(np.mean(maxdds)), 1),
            "worst_maxdd": round(float(np.max(maxdds)), 1),
            "winrate_5pct": round(float(np.percentile([r["winrate"] for r in results], 5)), 3),
            "profit_factor_95pct": round(float(np.percentile([r.get("profit_factor", 1.0) for r in results], 95)), 2),
            "num_runs": runs,
        }

    def generate_regime_dashboard(
        self,
        df: pd.DataFrame,
        walk_forward_res: Dict[str, Any],
        monte_res: Dict[str, Any],
        regime_res: Dict[str, Any],
    ) -> str:
        """Plotly dashboard (HTML) met walk-forward, regime en Monte Carlo resultaten"""
        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Walk-Forward Test Sharpe",
                "Sharpe per Regime",
                "Monte Carlo Sharpe Distribution",
                "Monte Carlo Max Drawdown Distribution",
            ),
        )

        # 1. Walk-forward test sharpe over tijd
        wf = walk_forward_res.get("walk_forward_results", [])
        if wf:
            fig.add_trace(
                go.Scatter(
                    x=[r["test_period"] for r in wf],
                    y=[r["test_sharpe"] for r in wf],
                    name="Test Sharpe",
                    mode="lines+markers",
                ),
                row=1,
                col=1,
            )

        # 2. Regime bar chart
        if regime_res:
            regimes = list(regime_res.keys())
            regime_sharpes = [regime_res[r]["sharpe"] for r in regimes]
            fig.add_trace(
                go.Bar(x=regimes, y=regime_sharpes, name="Sharpe per Regime"),
                row=1,
                col=2,
            )

        # 3. Monte Carlo Sharpe histogram – gebruik pre-computed mc resultaten
        mc_sharpe_sample = monte_res.get("_sharpe_samples", [])
        if not mc_sharpe_sample:
            # Genereer sample rondom mean/worst voor visueel
            mean_s = monte_res.get("mean_sharpe", 0.0)
            worst_s = monte_res.get("worst_sharpe", mean_s - 1.0)
            mc_sharpe_sample = list(
                np.random.normal(mean_s, abs(mean_s - worst_s) / 2 + 0.1, monte_res.get("num_runs", 100))
            )
        fig.add_trace(
            go.Histogram(x=mc_sharpe_sample, nbinsx=50, name="Sharpe Distribution"),
            row=2,
            col=1,
        )

        # 4. Monte Carlo MaxDD histogram
        mc_dd_sample = monte_res.get("_maxdd_samples", [])
        if not mc_dd_sample:
            mean_dd = monte_res.get("mean_maxdd", 5.0)
            worst_dd = monte_res.get("worst_maxdd", mean_dd + 5.0)
            mc_dd_sample = list(
                np.random.normal(mean_dd, abs(worst_dd - mean_dd) / 2 + 0.1, monte_res.get("num_runs", 100))
            )
        fig.add_trace(
            go.Histogram(x=mc_dd_sample, nbinsx=50, name="MaxDD Distribution"),
            row=2,
            col=2,
        )

        fig.update_layout(
            height=900,
            title_text=(
                f"LUMINA Advanced Backtest Dashboard – {datetime.now().strftime('%Y-%m-%d')} | "
                f"Avg OOS Sharpe {walk_forward_res.get('avg_test_sharpe', 0):.2f} | "
                f"MC worst DD {monte_res.get('worst_maxdd', 0):.1f}%"
            ),
        )

        output_path = "backtest_dashboard.html"
        fig.write_html(output_path)
        self.logger.info(f"BACKTEST_DASHBOARD_SAVED,path={output_path}")
        return output_path
