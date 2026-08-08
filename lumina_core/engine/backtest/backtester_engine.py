from __future__ import annotations

import json
import logging
import math
import random
import statistics
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from lumina_core.runtime_context import RuntimeContext
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.engine.backtest.order_book import DynamicSlippageModel
from lumina_core.engine.backtest.reality_gap import RealityGapTracker
from lumina_core.engine.backtest.backtester_fills import BacktesterFillsMixin, OrderBookReplay
from lumina_core.engine.backtest.backtester_validation import BacktesterValidationMixin


@dataclass(slots=True)
class BacktesterEngine(BacktesterFillsMixin, BacktesterValidationMixin):
    """Realistic execution backtester with Monte Carlo and walk-forward support.

    v2 upgrades:
      - DynamicSlippageModel (ATR-based, regime-aware, time-of-day-aware)
      - PurgedWalkForwardCV  (embargo-gap CV with Sharpe consistency metrics)
      - CombinatorialPurgedCV (PBO + Deflated Sharpe Ratio)
      - RealityGapTracker    (rolling SIM/REAL divergence with RED/YELLOW/GREEN bands)

    Fill simulation: ``backtester_fills``. Validation: ``backtester_validation``.
    """

    app: RuntimeContext
    point_value: float = 5.0
    commission_per_side_points: float = 0.25
    valuation_engine: ValuationEngine = field(default_factory=ValuationEngine)
    dynamic_slippage: DynamicSlippageModel = field(default_factory=DynamicSlippageModel)
    reality_gap_tracker: RealityGapTracker = field(default_factory=RealityGapTracker)

    def __post_init__(self) -> None:
        self.valuation_engine = ValuationEngine()
        instrument = str(getattr(self.app.engine.config, "instrument", "MES"))
        self.point_value = self.valuation_engine.point_value(instrument)
        tick_size = self.valuation_engine.tick_size(instrument) if hasattr(self.valuation_engine, "tick_size") else 0.25
        self.dynamic_slippage = DynamicSlippageModel(tick_size=tick_size)
        gap_history_path = Path("state/reality_gap_history.jsonl")
        self.reality_gap_tracker = RealityGapTracker(
            penalty_coeff=0.15,
            window=20,
            history_path=gap_history_path,
        )

    def run_snapshot_backtest(self, snapshot: list[dict[str, Any]]) -> dict[str, Any]:
        if len(snapshot) < 120:
            return {
                "trades": 0,
                "sharpe": 0.0,
                "winrate": 0.0,
                "maxdd": 0.0,
                "net_pnl": 0.0,
                "commission_paid": 0.0,
                "avg_slippage_ticks": 0.0,
                "monte_carlo": {"runs": 0, "mean_pnl": 0.0, "p05": 0.0, "p50": 0.0, "p95": 0.0},
                "walk_forward": {"windows": 0, "mean_pnl": 0.0, "mean_sharpe": 0.0, "mean_winrate": 0.0},
                "walk_forward_optimization": {"windows": 0, "mean_test_pnl": 0.0, "mean_test_sharpe": 0.0},
                "regime_attribution": {},
                "equity_curve": [50000.0],
            }

        base = self._run_single(snapshot, rng=random.Random(42), noise_std_points=0.0)
        monte_carlo = self._run_monte_carlo(snapshot, runs=1000)
        walk_forward = self._run_walk_forward(snapshot)
        walk_forward_opt = self._run_walk_forward_optimization(snapshot)
        purged_wf = self.run_purged_walk_forward(snapshot)
        cpcv = self.run_combinatorial_purged_cv(snapshot)

        return {
            **base,
            "monte_carlo": monte_carlo,
            "walk_forward": walk_forward,
            "walk_forward_optimization": walk_forward_opt,
            "purged_walk_forward": purged_wf,
            "combinatorial_purged_cv": cpcv,
        }

    def generate_full_report(
        self, snapshot: list[dict[str, Any]], output_dir: str = "journal/backtests"
    ) -> dict[str, Any]:
        core = self.run_snapshot_backtest(snapshot)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        report = {
            "generated_at": datetime.now().isoformat(),
            "snapshot_len": len(snapshot),
            "summary": {
                "trades": int(core.get("trades", 0)),
                "net_pnl": float(core.get("net_pnl", 0.0)),
                "sharpe": float(core.get("sharpe", 0.0)),
                "winrate": float(core.get("winrate", 0.0)),
                "maxdd": float(core.get("maxdd", 0.0)),
                "commission_paid": float(core.get("commission_paid", 0.0)),
                "avg_slippage_ticks": float(core.get("avg_slippage_ticks", 0.0)),
            },
            "regime_attribution": core.get("regime_attribution", {}),
            "monte_carlo": core.get("monte_carlo", {}),
            "walk_forward": core.get("walk_forward", {}),
            "walk_forward_optimization": core.get("walk_forward_optimization", {}),
            "equity_curve": core.get("equity_curve", []),
        }

        # Preserve flat keys for existing callers while also exposing structured report sections.
        report.update(core)

        json_path = out_dir / f"backtest_report_{ts}.json"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        plot_path = out_dir / f"backtest_dashboard_{ts}.html"
        self._build_dashboard_plot(report, plot_path)

        report["report_json_path"] = str(json_path)
        report["dashboard_plot_path"] = str(plot_path)
        return report

    def _build_dashboard_plot(self, report: dict[str, Any], output_path: Path) -> None:
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            equity = [float(x) for x in report.get("equity_curve", [])]
            mc = dict(report.get("monte_carlo", {}))
            regimes = dict(report.get("regime_attribution", {}))

            fig = make_subplots(
                rows=2,
                cols=2,
                subplot_titles=("Equity Curve", "Monte Carlo Percentiles", "Regime Attribution PnL", "Summary"),
                specs=[[{"type": "xy"}, {"type": "bar"}], [{"type": "bar"}, {"type": "table"}]],
            )

            if equity:
                fig.add_trace(go.Scatter(y=equity, mode="lines", name="equity"), row=1, col=1)

            fig.add_trace(
                go.Bar(
                    x=["P05", "P50", "P95"],
                    y=[float(mc.get("p05", 0.0)), float(mc.get("p50", 0.0)), float(mc.get("p95", 0.0))],
                    name="mc",
                ),
                row=1,
                col=2,
            )

            if regimes:
                keys = list(regimes.keys())
                vals = [float(regimes[k].get("net_pnl", 0.0)) for k in keys]
                fig.add_trace(go.Bar(x=keys, y=vals, name="regime_pnl"), row=2, col=1)

            summary = dict(report.get("summary", {}))
            fig.add_trace(
                go.Table(
                    header={"values": ["Metric", "Value"]},
                    cells={
                        "values": [
                            [
                                "trades",
                                "net_pnl",
                                "sharpe",
                                "winrate",
                                "maxdd",
                                "avg_slippage_ticks",
                                "commission_paid",
                            ],
                            [
                                str(summary.get("trades", 0)),
                                f"{float(summary.get('net_pnl', 0.0)):.2f}",
                                f"{float(summary.get('sharpe', 0.0)):.2f}",
                                f"{float(summary.get('winrate', 0.0)):.2%}",
                                f"{float(summary.get('maxdd', 0.0)):.2f}%",
                                f"{float(summary.get('avg_slippage_ticks', 0.0)):.2f}",
                                f"{float(summary.get('commission_paid', 0.0)):.2f}",
                            ],
                        ]
                    },
                ),
                row=2,
                col=2,
            )

            fig.update_layout(height=900, width=1400, title="Backtester Engine Report", showlegend=False)
            fig.write_html(str(output_path), include_plotlyjs="cdn")
        except Exception as exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/backtester_engine.py:542")
            output_path.write_text(
                json.dumps({"error": f"plot generation failed: {exc}"}, indent=2),
                encoding="utf-8",
            )

    @staticmethod
    def _sharpe(pnl_values: list[float]) -> float:
        if len(pnl_values) < 2:
            return 0.0
        std = statistics.pstdev(pnl_values)
        if std <= 1e-9:
            return 0.0
        return float((statistics.mean(pnl_values) / std) * math.sqrt(252.0))

    @staticmethod
    def _winrate(pnl_values: list[float]) -> float:
        if not pnl_values:
            return 0.0
        wins = len([x for x in pnl_values if x > 0])
        return float(wins / len(pnl_values))

    @staticmethod
    def _max_drawdown_pct(equity: list[float]) -> float:
        if not equity:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for value in equity:
            peak = max(peak, value)
            if peak > 0:
                dd = (peak - value) / peak
                max_dd = max(max_dd, dd)
        return float(max_dd * 100.0)

    @staticmethod
    def _percentile(sorted_values: list[float], q: float) -> float:
        if not sorted_values:
            return 0.0
        idx = (len(sorted_values) - 1) * q
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return float(sorted_values[lo])
        weight = idx - lo
        return float(sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight)

    # ------------------------------------------------------------------
    # Reality Gap Tracking (delegates to RealityGapTracker)
    # ------------------------------------------------------------------

    def record_reality_gap(
        self,
        *,
        sim_sharpe: float,
        real_sharpe: float,
        gap_history_path: Path | None = None,
    ) -> float:
        """Observe a SIM vs REAL Sharpe pair and return the instantaneous penalty.

        The penalty = max(0, sim_sharpe - real_sharpe) × coeff.

        Also stores the observation in the rolling tracker so that
        ``get_reality_gap_penalty()`` returns an EWM-smoothed value.
        """
        if gap_history_path is not None:
            self.reality_gap_tracker.history_path = gap_history_path
        return self.reality_gap_tracker.observe(sim_sharpe, real_sharpe)

    def get_reality_gap_penalty(self) -> float:
        """Return the current dynamic penalty from the rolling tracker.

        Uses regime-adaptive coefficient (2× when RED, 1.5× when YELLOW).
        Suitable for passing to ``calculate_fitness(reality_gap_penalty=...)``.
        """
        return self.reality_gap_tracker.dynamic_penalty()

    def compute_rolling_reality_gap(
        self,
        *,
        gap_history_path: Path | None = None,
        window: int = 20,
    ) -> dict[str, Any]:
        """Return rolling reality-gap statistics.

        Loads history from file if needed, then delegates to
        ``RealityGapTracker.rolling_stats()``.
        """
        if gap_history_path is not None:
            self.reality_gap_tracker.history_path = gap_history_path
        if gap_history_path is not None and not self.reality_gap_tracker._observations:
            self.reality_gap_tracker.load_history(gap_history_path)
        if window != self.reality_gap_tracker.window:
            self.reality_gap_tracker.window = window
        return self.reality_gap_tracker.rolling_stats()


__all__ = ["BacktesterEngine", "OrderBookReplay", "BacktesterFillsMixin", "BacktesterValidationMixin"]
