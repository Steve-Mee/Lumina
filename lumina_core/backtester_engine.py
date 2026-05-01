from __future__ import annotations

import json
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
from lumina_core.engine.backtest.cross_validation import PurgedWalkForwardCV, CombinatorialPurgedCV
from lumina_core.engine.backtest.reality_gap import RealityGapTracker


@dataclass(slots=True)
class BacktesterEngine:
    """Realistic execution backtester with Monte Carlo and walk-forward support.

    v2 upgrades:
      - DynamicSlippageModel (ATR-based, regime-aware, time-of-day-aware)
      - PurgedWalkForwardCV  (embargo-gap CV with Sharpe consistency metrics)
      - CombinatorialPurgedCV (PBO + Deflated Sharpe Ratio)
      - RealityGapTracker    (rolling SIM/REAL divergence with RED/YELLOW/GREEN bands)
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

    def _run_single(
        self,
        snapshot: list[dict[str, Any]],
        *,
        rng: random.Random,
        noise_std_points: float,
        min_confluence_override: float | None = None,
        slippage_scale: float = 1.0,
        include_gap_events: bool = False,
        gap_event_prob: float = 0.002,
        gap_std_points: float = 2.0,
        use_dynamic_slippage: bool = True,
    ) -> dict[str, Any]:
        pnl_values: list[float] = []
        equity: list[float] = [50000.0]
        slippage_ticks: list[float] = []
        commission_paid = 0.0
        gap_events = 0
        regime_attribution: dict[str, dict[str, float]] = {}
        regime_counts: dict[str, int] = {}

        position = 0
        entry_price = 0.0
        entry_regime = "NEUTRAL"
        pending_side = 0
        pending_age = 0

        dream_snapshot = self.app.get_current_dream_snapshot()
        signal = str(dream_snapshot.get("signal", "HOLD"))
        confluence = float(dream_snapshot.get("confluence_score", 0.0))
        min_confluence = float(
            min_confluence_override if min_confluence_override is not None else getattr(self.app, "MIN_CONFLUENCE", 0.8)
        )

        for i in range(60, len(snapshot)):
            row = snapshot[i]
            raw_price = float(row.get("close", row.get("last", 0.0)))
            if raw_price <= 0:
                continue

            price = raw_price + rng.gauss(0.0, noise_std_points)
            if include_gap_events and rng.random() < gap_event_prob:
                price += rng.gauss(0.0, gap_std_points)
                gap_events += 1
            volume = float(row.get("volume", 0.0))
            recent = snapshot[max(0, i - 30) : i]
            bar_history = snapshot[max(0, i - self.dynamic_slippage.atr_window - 1) : i + 1]
            avg_volume = self._avg_volume(recent)
            regime = self._regime_from_snapshot(snapshot[: i + 1])
            regime_label = self._normalize_regime(regime)
            regime_counts[regime_label] = regime_counts.get(regime_label, 0) + 1

            if position == 0 and pending_side == 0 and signal in {"BUY", "SELL"} and confluence > min_confluence:
                pending_side = 1 if signal == "BUY" else -1
                pending_age = 0

            if pending_side != 0:
                pending_age += 1
                if self._queue_filled(rng, volume, avg_volume, pending_age, regime):
                    if use_dynamic_slippage:
                        slip_ticks = self.dynamic_slippage.slippage_for_bar(
                            row, bar_history,
                            quantity=1.0,
                            avg_volume=avg_volume,
                            regime=regime_label,
                        ) * slippage_scale
                    else:
                        slip_ticks = self._slippage_ticks(volume, avg_volume, regime, slippage_scale=slippage_scale)
                    slippage_ticks.append(slip_ticks)
                    fill_price = self._apply_entry_fill(price, pending_side, slip_ticks)
                    position = pending_side
                    entry_price = fill_price
                    entry_regime = regime_label
                    pending_side = 0
                    pending_age = 0
                elif pending_age > 3:
                    pending_side = 0
                    pending_age = 0

            if position != 0:
                stop = float(dream_snapshot.get("stop", 0.0))
                target = float(dream_snapshot.get("target", 0.0))
                hit_stop = (position > 0 and stop > 0 and price <= stop) or (
                    position < 0 and stop > 0 and price >= stop
                )
                hit_target = (position > 0 and target > 0 and price >= target) or (
                    position < 0 and target > 0 and price <= target
                )

                if hit_stop or hit_target:
                    if use_dynamic_slippage:
                        slip_ticks = self.dynamic_slippage.slippage_for_bar(
                            row, bar_history,
                            quantity=1.0,
                            avg_volume=avg_volume,
                            regime=regime_label,
                        ) * slippage_scale
                    else:
                        slip_ticks = self._slippage_ticks(volume, avg_volume, regime, slippage_scale=slippage_scale)
                    slippage_ticks.append(slip_ticks)
                    exit_price = self._apply_exit_fill(price, position, slip_ticks)

                    gross = (exit_price - entry_price) * position * self.point_value
                    trade_fee = 2.0 * self._commission_dollars_one_side()
                    commission_paid += trade_fee
                    net = gross - trade_fee

                    pnl_values.append(net)
                    equity.append(equity[-1] + net)
                    bucket = regime_attribution.setdefault(
                        entry_regime,
                        {"trades": 0.0, "wins": 0.0, "net_pnl": 0.0, "avg_pnl": 0.0, "winrate": 0.0},
                    )
                    bucket["trades"] += 1.0
                    if net > 0:
                        bucket["wins"] += 1.0
                    bucket["net_pnl"] += float(net)

                    position = 0
                    entry_price = 0.0
                    entry_regime = "NEUTRAL"

        for stats in regime_attribution.values():
            trades = max(1.0, stats["trades"])
            stats["avg_pnl"] = float(stats["net_pnl"] / trades)
            stats["winrate"] = float(stats["wins"] / trades)

        sharpe = self._sharpe(pnl_values)
        winrate = self._winrate(pnl_values)
        maxdd = self._max_drawdown_pct(equity)
        avg_slip = statistics.mean(slippage_ticks) if slippage_ticks else 0.0

        return {
            "trades": len(pnl_values),
            "sharpe": sharpe,
            "winrate": winrate,
            "maxdd": maxdd,
            "net_pnl": float(sum(pnl_values)),
            "commission_paid": float(commission_paid),
            "avg_slippage_ticks": float(avg_slip),
            "equity_curve": [float(x) for x in equity],
            "regime_attribution": regime_attribution,
            "regime_summary": regime_counts,
            "gap_events": int(gap_events),
        }

    def _run_monte_carlo(self, snapshot: list[dict[str, Any]], runs: int) -> dict[str, Any]:
        outcomes: list[float] = []
        gap_counts: list[int] = []
        for seed in range(runs):
            run = self._run_single(
                snapshot,
                rng=random.Random(1000 + seed),
                noise_std_points=0.15,
                include_gap_events=True,
                gap_event_prob=0.002,
                gap_std_points=2.5,
            )
            outcomes.append(float(run.get("net_pnl", 0.0)))
            gap_counts.append(int(run.get("gap_events", 0)))

        if not outcomes:
            return {"runs": 0, "mean_pnl": 0.0, "p05": 0.0, "p50": 0.0, "p95": 0.0, "avg_gap_events": 0.0}

        ordered = sorted(outcomes)
        return {
            "runs": runs,
            "mean_pnl": float(statistics.mean(outcomes)),
            "p05": float(self._percentile(ordered, 0.05)),
            "p50": float(self._percentile(ordered, 0.50)),
            "p95": float(self._percentile(ordered, 0.95)),
            "avg_gap_events": float(statistics.mean(gap_counts) if gap_counts else 0.0),
        }

    def _run_walk_forward(self, snapshot: list[dict[str, Any]]) -> dict[str, Any]:
        train_size = 2400
        test_size = 600
        step = 600
        if len(snapshot) < (train_size + test_size):
            return {"windows": 0, "mean_pnl": 0.0, "mean_sharpe": 0.0, "mean_winrate": 0.0}

        pnls: list[float] = []
        sharpes: list[float] = []
        winrates: list[float] = []

        start = 0
        while (start + train_size + test_size) <= len(snapshot):
            test_chunk = snapshot[start + train_size : start + train_size + test_size]
            run = self._run_single(test_chunk, rng=random.Random(2000 + start), noise_std_points=0.05)
            pnls.append(float(run.get("net_pnl", 0.0)))
            sharpes.append(float(run.get("sharpe", 0.0)))
            winrates.append(float(run.get("winrate", 0.0)))
            start += step

        if not pnls:
            return {"windows": 0, "mean_pnl": 0.0, "mean_sharpe": 0.0, "mean_winrate": 0.0}

        return {
            "windows": len(pnls),
            "mean_pnl": float(statistics.mean(pnls)),
            "mean_sharpe": float(statistics.mean(sharpes)),
            "mean_winrate": float(statistics.mean(winrates)),
        }

    def _run_walk_forward_optimization(self, snapshot: list[dict[str, Any]]) -> dict[str, Any]:
        bars_per_day = self._infer_bars_per_day(snapshot)
        train_bars = 30 * bars_per_day
        test_bars = 5 * bars_per_day
        step_bars = max(1, test_bars)
        if len(snapshot) < (train_bars + test_bars):
            return {"windows": 0, "mean_test_pnl": 0.0, "mean_test_sharpe": 0.0, "details": []}

        confluence_grid = [0.65, 0.75, 0.85, 0.95]
        slippage_grid = [0.9, 1.0, 1.1]
        details: list[dict[str, Any]] = []
        test_pnls: list[float] = []
        test_sharpes: list[float] = []

        start = 0
        while (start + train_bars + test_bars) <= len(snapshot):
            train_chunk = snapshot[start : start + train_bars]
            test_chunk = snapshot[start + train_bars : start + train_bars + test_bars]

            best_score = -1e18
            best_params = {"min_confluence": 0.8, "slippage_scale": 1.0}
            for mc in confluence_grid:
                for slip_scale in slippage_grid:
                    train_run = self._run_single(
                        train_chunk,
                        rng=random.Random(3000 + start + int(mc * 100) + int(slip_scale * 100)),
                        noise_std_points=0.03,
                        min_confluence_override=mc,
                        slippage_scale=slip_scale,
                    )
                    score = float(train_run.get("net_pnl", 0.0)) - float(train_run.get("maxdd", 0.0)) * 20.0
                    if score > best_score:
                        best_score = score
                        best_params = {"min_confluence": mc, "slippage_scale": slip_scale}

            test_run = self._run_single(
                test_chunk,
                rng=random.Random(4000 + start),
                noise_std_points=0.05,
                min_confluence_override=float(best_params["min_confluence"]),
                slippage_scale=float(best_params["slippage_scale"]),
            )
            test_pnl = float(test_run.get("net_pnl", 0.0))
            test_sharpe = float(test_run.get("sharpe", 0.0))
            test_pnls.append(test_pnl)
            test_sharpes.append(test_sharpe)

            details.append(
                {
                    "window_start": start,
                    "train_bars": train_bars,
                    "test_bars": test_bars,
                    "best_params": best_params,
                    "test_net_pnl": test_pnl,
                    "test_sharpe": test_sharpe,
                    "test_winrate": float(test_run.get("winrate", 0.0)),
                }
            )
            start += step_bars

        if not details:
            return {"windows": 0, "mean_test_pnl": 0.0, "mean_test_sharpe": 0.0, "details": []}

        return {
            "windows": len(details),
            "train_days": 30,
            "test_days": 5,
            "bars_per_day": bars_per_day,
            "mean_test_pnl": float(statistics.mean(test_pnls)),
            "mean_test_sharpe": float(statistics.mean(test_sharpes)),
            "details": details,
        }

    def _regime_from_snapshot(self, rows: list[dict[str, Any]]) -> str:
        try:
            if hasattr(self.app, "detect_market_regime"):
                import pandas as pd

                df = pd.DataFrame(rows)
                if not df.empty and {"open", "high", "low", "close", "volume"}.issubset(df.columns):
                    return str(self.app.detect_market_regime(df))
        except Exception:
            pass
        return "NEUTRAL"

    @staticmethod
    def _avg_volume(rows: list[dict[str, Any]]) -> float:
        vols = [float(r.get("volume", 0.0)) for r in rows if float(r.get("volume", 0.0)) > 0.0]
        return statistics.mean(vols) if vols else 1.0

    def _queue_filled(self, rng: random.Random, volume: float, avg_volume: float, age: int, regime: str) -> bool:
        return self.valuation_engine.should_fill_order(
            rng=rng,
            volume=volume,
            avg_volume=avg_volume,
            pending_age=age,
            regime=regime,
        )

    def _slippage_ticks(self, volume: float, avg_volume: float, regime: str, slippage_scale: float) -> float:
        return self.valuation_engine.slippage_ticks(
            volume=volume,
            avg_volume=avg_volume,
            regime=regime,
            slippage_scale=slippage_scale,
        )

    @staticmethod
    def _normalize_regime(raw: str) -> str:
        text = str(raw).upper()
        if any(x in text for x in ("TREND", "BREAKOUT", "MOMENTUM")):
            return "TRENDING"
        if any(x in text for x in ("RANGE", "SIDEWAYS", "MEAN")):
            return "RANGING"
        if any(x in text for x in ("VOLATILE", "CHAOS", "HIGH_VOL", "HIGH_VOLATILITY")):
            return "HIGH_VOLATILITY"
        if "NEWS" in text:
            return "NEWS_DRIVEN"
        if "ROLLOVER" in text:
            return "ROLLOVER"
        if "LOW_LIQ" in text:
            return "LOW_LIQUIDITY"
        if any(x in text for x in ("LOW_VOL", "CALM")):
            return "LOW_VOL"
        return "NEUTRAL"

    def _infer_bars_per_day(self, snapshot: list[dict[str, Any]]) -> int:
        try:
            timestamps: list[datetime] = []
            for row in snapshot[: min(len(snapshot), 5000)]:
                ts = row.get("timestamp")
                if ts is None:
                    continue
                timestamps.append(datetime.fromisoformat(str(ts).replace("Z", "+00:00")))
            if len(timestamps) < 3:
                return 1440
            timestamps.sort()
            deltas = [(timestamps[i] - timestamps[i - 1]).total_seconds() for i in range(1, len(timestamps))]
            median_delta = statistics.median([d for d in deltas if d > 0])
            if median_delta <= 0:
                return 1440
            return max(1, int(round(86400.0 / median_delta)))
        except Exception:
            return 1440

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
            output_path.write_text(
                json.dumps({"error": f"plot generation failed: {exc}"}, indent=2),
                encoding="utf-8",
            )

    def _apply_entry_fill(self, price: float, side: int, slip_ticks: float) -> float:
        instrument = str(getattr(self.app.engine.config, "instrument", "MES"))
        return self.valuation_engine.apply_entry_fill(
            symbol=instrument,
            price=price,
            side=side,
            slippage_ticks=slip_ticks,
        )

    def _apply_exit_fill(self, price: float, side: int, slip_ticks: float) -> float:
        instrument = str(getattr(self.app.engine.config, "instrument", "MES"))
        return self.valuation_engine.apply_exit_fill(
            symbol=instrument,
            price=price,
            side=side,
            slippage_ticks=slip_ticks,
        )

    def _commission_dollars_one_side(self) -> float:
        instrument = str(getattr(self.app.engine.config, "instrument", "MES"))
        return self.valuation_engine.commission_dollars(symbol=instrument, quantity=1, sides=1)

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
    # Purged Walk-Forward Cross-Validation (delegates to PurgedWalkForwardCV)
    # ------------------------------------------------------------------

    def run_purged_walk_forward(
        self,
        snapshot: list[dict[str, Any]],
        *,
        train_days: int = 30,
        test_days: int = 5,
        embargo_days: int = 1,
    ) -> dict[str, Any]:
        """Walk-forward CV with embargo gap, Sharpe consistency, and degradation stats.

        Delegates to ``PurgedWalkForwardCV`` from
        ``lumina_core.engine.backtest.cross_validation``.

        New in v2: sharpe_positive_pct, sharpe_p25/p75, worst_pnl, best_pnl.
        """
        bars_per_day = self._infer_bars_per_day(snapshot)
        train_bars = train_days * bars_per_day
        test_bars = test_days * bars_per_day
        embargo_bars = max(1, embargo_days * bars_per_day)

        cv = PurgedWalkForwardCV(
            train_bars=train_bars,
            test_bars=test_bars,
            embargo_bars=embargo_bars,
        )

        def _scorer(chunk: list[dict[str, Any]]) -> dict[str, Any]:
            return self._run_single(
                chunk,
                rng=random.Random(abs(hash(str(len(chunk)))) % (2**31)),
                noise_std_points=0.05,
            )

        result = cv.run(snapshot, _scorer)
        result["train_days"] = train_days
        result["test_days"] = test_days
        return result

    # ------------------------------------------------------------------
    # Combinatorial Purged CV — PBO + Deflated Sharpe Ratio
    # ------------------------------------------------------------------

    def run_combinatorial_purged_cv(
        self,
        snapshot: list[dict[str, Any]],
        *,
        n_splits: int = 6,
        n_test_folds: int = 1,
        embargo_pct: float = 0.01,
    ) -> dict[str, Any]:
        """Combinatorial Purged Cross-Validation.

        Produces Probability of Backtest Overfitting (PBO) and
        Deflated Sharpe Ratio (DSR) — the two primary anti-overfitting
        metrics from the AFML framework.

        PBO < 0.25 → low overfitting risk
        DSR > 0    → strategy survives multiple-testing correction

        Delegates to ``CombinatorialPurgedCV`` from
        ``lumina_core.engine.backtest.cross_validation``.
        """
        cpcv = CombinatorialPurgedCV(
            n_splits=n_splits,
            n_test_folds=n_test_folds,
            embargo_pct=embargo_pct,
        )

        seed_base = abs(hash(str(len(snapshot)))) % (2**24)

        def _scorer(chunk: list[dict[str, Any]]) -> dict[str, Any]:
            return self._run_single(
                chunk,
                rng=random.Random(seed_base + len(chunk)),
                noise_std_points=0.05,
            )

        return cpcv.run(snapshot, _scorer)

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


# ---------------------------------------------------------------------------
# P3: OrderBookReplay — ATR-based bid/ask spread simulator
# ---------------------------------------------------------------------------


class OrderBookReplay:
    """Simulates realistic bid-ask spreads and market impact from OHLCV bars.

    Replaces pure-Gaussian slippage with a model that accounts for:
      - Intraday liquidity patterns (open/midday/close spread multipliers)
      - ATR-scaled spread width (wider in volatile regimes)
      - Power-law market impact for position sizing (Almgren-Chriss simplified)

    Designed to be used inside ``BacktesterEngine._run_single()`` as a
    drop-in replacement for ``ValuationEngine.slippage_ticks()``.
    """

    def __init__(
        self,
        *,
        spread_atr_ratio: float = 0.10,
        market_impact_alpha: float = 0.5,
        market_impact_beta: float = 0.6,
        time_of_day_multipliers: dict[str, float] | None = None,
    ) -> None:
        self.spread_atr_ratio = float(spread_atr_ratio)
        self.market_impact_alpha = float(market_impact_alpha)
        self.market_impact_beta = float(market_impact_beta)
        self.time_of_day_multipliers: dict[str, float] = time_of_day_multipliers or {
            "open": 2.5,     # First 30 min — wide spreads
            "midday": 1.0,   # 10:30–14:00 EST — normal liquidity
            "close": 2.0,    # Last 30 min — wider again
        }

    def spread_ticks(
        self,
        bar: dict[str, Any],
        atr: float,
        tick_size: float = 0.25,
        *,
        time_period: str = "midday",
    ) -> float:
        """Estimate half-spread in ticks for the given bar.

        Args:
            bar:         OHLCV dict with 'high', 'low', 'close' keys.
            atr:         Average True Range in price points.
            tick_size:   Instrument tick size (0.25 for MES).
            time_period: 'open', 'midday', or 'close'.

        Returns:
            Half-spread in ticks (add to entry, subtract from exit).
        """
        if atr <= 0 or tick_size <= 0:
            return 1.0

        spread_points = max(tick_size, atr * self.spread_atr_ratio)
        multiplier = self.time_of_day_multipliers.get(time_period, 1.0)
        half_spread_ticks = (spread_points * multiplier) / tick_size
        return max(1.0, float(half_spread_ticks))

    def market_impact_ticks(
        self,
        quantity: float,
        avg_volume: float,
        tick_size: float = 0.25,
    ) -> float:
        """Estimate market-impact cost in ticks using a power-law model.

        Impact = alpha * (qty / avg_volume) ^ beta

        Returns 0.0 when avg_volume <= 0 (e.g., synthetic data).
        """
        if avg_volume <= 0 or quantity <= 0:
            return 0.0

        volume_ratio = float(quantity) / max(float(avg_volume), 1.0)
        impact_points = self.market_impact_alpha * (volume_ratio ** self.market_impact_beta)
        return max(0.0, impact_points / tick_size)

    def total_slippage_ticks(
        self,
        bar: dict[str, Any],
        atr: float,
        quantity: float = 1.0,
        avg_volume: float = 1000.0,
        tick_size: float = 0.25,
        *,
        time_period: str = "midday",
    ) -> float:
        """Combined half-spread + market-impact in ticks."""
        spread = self.spread_ticks(bar, atr, tick_size, time_period=time_period)
        impact = self.market_impact_ticks(quantity, avg_volume, tick_size)
        return spread + impact
