"""Backtester Monte Carlo / walk-forward / purged CV helpers.

Extracted from ``backtester_engine`` (Wave B2 PR-C0).
"""
from __future__ import annotations

import logging
import random
import statistics
from datetime import datetime
from typing import Any

from lumina_core.engine.backtest.cross_validation import CombinatorialPurgedCV, PurgedWalkForwardCV


class BacktesterValidationMixin:
    """MC / WF / CPCV validation paths for ``BacktesterEngine``."""

    __slots__ = ()

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
            logging.exception("Unhandled broad exception fallback in lumina_core/backtester_engine.py:472")
            return 1440

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
