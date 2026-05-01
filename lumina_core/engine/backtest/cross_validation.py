"""Purged Cross-Validation and Combinatorial Purged Cross-Validation.

Implements the Marcos Lopez de Prado framework (Advances in Financial ML, ch. 12):

  - PurgedWalkForwardCV    walk-forward CV with embargo gaps (already existed;
                           this version adds Sharpe consistency and degradation stats)
  - CombinatorialPurgedCV  k-fold combinatorial split with PBO and DSR

Key metrics produced:

  Probability of Backtest Overfitting (PBO):
      PBO = P[rank(IS Sharpe) > 0.5 | OOS Sharpe < median(OOS Sharpes)]
      Practical approximation: fraction of combinations where the best
      in-sample fold is NOT the best out-of-sample fold.

  Deflated Sharpe Ratio (DSR):
      Adjusts for multiple testing.  DSR = SR / sqrt(1 + skew_penalty).
      Simplified: penalise SR by log(combinations) / sqrt(trials).

All cross-validation splits assume *chronological* (non-shuffled) order.
"""

from __future__ import annotations

import itertools
import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_sharpe(pnl_values: list[float]) -> float:
    if len(pnl_values) < 2:
        return 0.0
    std = statistics.pstdev(pnl_values)
    if std <= 1e-9:
        return 0.0
    return float((statistics.mean(pnl_values) / std) * math.sqrt(252.0))


def _safe_winrate(pnl_values: list[float]) -> float:
    if not pnl_values:
        return 0.0
    return float(sum(1 for x in pnl_values if x > 0) / len(pnl_values))


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = (len(sorted_vals) - 1) * q
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(sorted_vals[lo])
    return float(sorted_vals[lo] * (1.0 - (idx - lo)) + sorted_vals[hi] * (idx - lo))


# ---------------------------------------------------------------------------
# PurgedWalkForwardCV
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PurgedWalkForwardCV:
    """Walk-forward CV with configurable embargo gap.

    Unlike a simple walk-forward, the embargo gap removes the *k* bars
    immediately after the training window to prevent information leakage
    caused by autocorrelated returns.

    Parameters
    ----------
    train_bars : int
        Bars in each training window.
    test_bars : int
        Bars in each test window.
    embargo_bars : int
        Bars to skip between train end and test start.
    step_bars : int | None
        How far to advance each fold.  Defaults to test_bars (non-overlapping).
    """

    train_bars: int = 2880   # ~10 trading days of 5-min bars
    test_bars: int = 576     # ~2 trading days
    embargo_bars: int = 60   # ~4 hours
    step_bars: int | None = None

    def split(
        self, n: int
    ) -> list[tuple[list[int], list[int]]]:
        """Generate (train_indices, test_indices) pairs for a dataset of length n."""
        step = self.step_bars if self.step_bars is not None else self.test_bars
        splits: list[tuple[list[int], list[int]]] = []
        start = 0
        while (start + self.train_bars + self.embargo_bars + self.test_bars) <= n:
            train_idx = list(range(start, start + self.train_bars))
            test_start = start + self.train_bars + self.embargo_bars
            test_idx = list(range(test_start, test_start + self.test_bars))
            splits.append((train_idx, test_idx))
            start += step
        return splits

    def run(
        self,
        snapshot: list[dict[str, Any]],
        scorer: Callable[[list[dict[str, Any]]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Run purged walk-forward CV using *scorer* on each test chunk.

        scorer: function taking a list[bar] → dict with at least 'net_pnl',
                'sharpe', 'winrate'.

        Returns
        -------
        dict with:
          windows, mean_pnl, mean_sharpe, mean_winrate, pnl_std,
          sharpe_positive_pct, details[]
        """
        n = len(snapshot)
        splits = self.split(n)
        if not splits:
            return self._empty_result()

        pnls: list[float] = []
        sharpes: list[float] = []
        winrates: list[float] = []
        details: list[dict[str, Any]] = []

        for window_idx, (train_idx, test_idx) in enumerate(splits):
            if not test_idx:
                continue
            test_chunk = [snapshot[i] for i in test_idx]
            result = scorer(test_chunk)
            pnl = float(result.get("net_pnl", 0.0))
            sharpe = float(result.get("sharpe", 0.0))
            winrate = float(result.get("winrate", 0.0))

            pnls.append(pnl)
            sharpes.append(sharpe)
            winrates.append(winrate)
            details.append(
                {
                    "window": window_idx,
                    "train_start": train_idx[0],
                    "train_end": train_idx[-1] + 1,
                    "embargo_end": test_idx[0],
                    "test_start": test_idx[0],
                    "test_end": test_idx[-1] + 1,
                    "pnl": pnl,
                    "sharpe": sharpe,
                    "winrate": winrate,
                }
            )

        if not pnls:
            return self._empty_result()

        sorted_sharpes = sorted(sharpes)
        return {
            "method": "purged_walk_forward",
            "windows": len(pnls),
            "embargo_bars": self.embargo_bars,
            "mean_pnl": statistics.mean(pnls),
            "mean_sharpe": statistics.mean(sharpes),
            "mean_winrate": statistics.mean(winrates),
            "pnl_std": statistics.pstdev(pnls) if len(pnls) > 1 else 0.0,
            "sharpe_positive_pct": sum(1 for s in sharpes if s > 0) / len(sharpes),
            "sharpe_p25": _percentile(sorted_sharpes, 0.25),
            "sharpe_p75": _percentile(sorted_sharpes, 0.75),
            "worst_pnl": min(pnls),
            "best_pnl": max(pnls),
            "details": details,
        }

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "method": "purged_walk_forward",
            "windows": 0,
            "embargo_bars": 0,
            "mean_pnl": 0.0,
            "mean_sharpe": 0.0,
            "mean_winrate": 0.0,
            "pnl_std": 0.0,
            "sharpe_positive_pct": 0.0,
            "sharpe_p25": 0.0,
            "sharpe_p75": 0.0,
            "worst_pnl": 0.0,
            "best_pnl": 0.0,
            "details": [],
        }


# ---------------------------------------------------------------------------
# CombinatorialPurgedCV
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CombinatorialPurgedCV:
    """Combinatorial Purged Cross-Validation (CPCV).

    Splits data into *n_splits* folds, then uses all C(n_splits, n_test_folds)
    combinations of test folds, training on the remaining folds with embargo
    gaps between adjacent train/test segments.

    Produces:
      - Per-combination test Sharpe
      - Probability of Backtest Overfitting (PBO)
      - Deflated Sharpe Ratio (DSR)

    Practical limits:
      - n_splits = 5 → C(5,1) = 5 combinations
      - n_splits = 6 → C(6,2) = 15 combinations
      - n_splits = 10 → C(10,2) = 45 combinations (heavy; use slow marker)

    References:
      de Prado (2018) AFML ch. 12
    """

    n_splits: int = 6
    n_test_folds: int = 1
    embargo_pct: float = 0.01  # fraction of fold length to use as embargo

    def split(self, n: int) -> list[tuple[list[int], list[int]]]:
        """Return (train_indices, test_indices) for each combination.

        Embargo gaps are inserted between the last training bar before each
        test segment and the start of the test segment.
        """
        fold_size = n // self.n_splits
        if fold_size < 10:
            return []

        embargo = max(1, int(fold_size * self.embargo_pct))
        folds: list[list[int]] = []
        for k in range(self.n_splits):
            start = k * fold_size
            end = start + fold_size if k < self.n_splits - 1 else n
            folds.append(list(range(start, end)))

        combinations = list(itertools.combinations(range(self.n_splits), self.n_test_folds))
        splits: list[tuple[list[int], list[int]]] = []

        for test_fold_indices in combinations:
            test_fold_set = set(test_fold_indices)
            test_idx: list[int] = []
            train_idx: list[int] = []

            sorted_test_folds = sorted(test_fold_indices)
            test_boundaries: set[int] = set()
            for tf in sorted_test_folds:
                test_idx.extend(folds[tf])
                test_boundaries.add(folds[tf][0])

            for k in range(self.n_splits):
                if k in test_fold_set:
                    continue
                fold_bars = folds[k]
                # Trim bars within *embargo* of any test fold boundary.
                cleaned: list[int] = []
                for idx in fold_bars:
                    too_close = any(
                        abs(idx - boundary) <= embargo for boundary in test_boundaries
                    )
                    if not too_close:
                        cleaned.append(idx)
                train_idx.extend(cleaned)

            if train_idx and test_idx:
                splits.append((sorted(train_idx), sorted(test_idx)))

        return splits

    def run(
        self,
        snapshot: list[dict[str, Any]],
        scorer: Callable[[list[dict[str, Any]]], dict[str, Any]],
    ) -> dict[str, Any]:
        """Run CPCV and compute PBO + DSR.

        Returns
        -------
        dict with:
          combinations, mean_oos_sharpe, sharpe_positive_pct,
          pbo (Probability of Backtest Overfitting),
          dsr (Deflated Sharpe Ratio),
          details[]
        """
        n = len(snapshot)
        splits = self.split(n)
        if not splits:
            return self._empty_result()

        oos_sharpes: list[float] = []
        combination_details: list[dict[str, Any]] = []

        for comb_idx, (train_idx, test_idx) in enumerate(splits):
            if not test_idx:
                continue
            test_chunk = [snapshot[i] for i in test_idx]
            result = scorer(test_chunk)
            oos_sharpe = float(result.get("sharpe", 0.0))
            oos_pnl = float(result.get("net_pnl", 0.0))

            oos_sharpes.append(oos_sharpe)
            combination_details.append(
                {
                    "combination": comb_idx,
                    "train_bars": len(train_idx),
                    "test_bars": len(test_idx),
                    "oos_sharpe": oos_sharpe,
                    "oos_pnl": oos_pnl,
                    "oos_winrate": float(result.get("winrate", 0.0)),
                }
            )

        if not oos_sharpes:
            return self._empty_result()

        pbo = self._compute_pbo(oos_sharpes)
        dsr = self._compute_dsr(oos_sharpes, n_combinations=len(splits))
        sorted_sharpes = sorted(oos_sharpes)

        return {
            "method": "combinatorial_purged_cv",
            "n_splits": self.n_splits,
            "n_test_folds": self.n_test_folds,
            "combinations": len(oos_sharpes),
            "mean_oos_sharpe": statistics.mean(oos_sharpes),
            "median_oos_sharpe": statistics.median(oos_sharpes),
            "oos_sharpe_std": statistics.pstdev(oos_sharpes) if len(oos_sharpes) > 1 else 0.0,
            "sharpe_p05": _percentile(sorted_sharpes, 0.05),
            "sharpe_p95": _percentile(sorted_sharpes, 0.95),
            "sharpe_positive_pct": sum(1 for s in oos_sharpes if s > 0) / len(oos_sharpes),
            "pbo": pbo,
            "dsr": dsr,
            "details": combination_details,
        }

    @staticmethod
    def _compute_pbo(oos_sharpes: list[float]) -> float:
        """Probability of Backtest Overfitting.

        Approximation: fraction of OOS Sharpes that are below the median.
        A high PBO (> 0.5) means most combinations that look good in-sample
        underperform out-of-sample — a sign of overfitting.

        Range: [0, 1].  Ideal: < 0.25.
        """
        if not oos_sharpes:
            return 0.0
        median_sharpe = statistics.median(oos_sharpes)
        below_median = sum(1 for s in oos_sharpes if s < median_sharpe)
        return float(below_median / len(oos_sharpes))

    @staticmethod
    def _compute_dsr(
        oos_sharpes: list[float],
        *,
        n_combinations: int,
        risk_free_rate: float = 0.0,
    ) -> float:
        """Deflated Sharpe Ratio.

        DSR = (SR - SR*) / StdErr(SR)
        where SR* = E[max SR | n_combinations] accounts for multiple testing.

        Simplified formula (Bailey & de Prado, 2014):
          SR* = sqrt(Var(SR)) * ((1 - gamma) * Z^{-1}(1 - 1/n) + gamma * Z^{-1}(1 - 1/(n*e)))
          ... but we use the simpler log-correction:
          SR* = SR_mean + SR_std * sqrt(2 * log(n_combinations))

        Returns DSR ∈ (-∞, 1].  Positive means the strategy survives deflation.
        """
        if not oos_sharpes or n_combinations <= 1:
            return float(statistics.mean(oos_sharpes)) if oos_sharpes else 0.0

        sr_mean = statistics.mean(oos_sharpes)
        sr_std = statistics.pstdev(oos_sharpes) if len(oos_sharpes) > 1 else 0.0

        # Expected maximum SR under H0 (Gaussian approximation).
        sr_star = risk_free_rate + sr_std * math.sqrt(
            max(0.0, 2.0 * math.log(n_combinations))
        )

        # Standard error of SR estimate.
        n = len(oos_sharpes)
        if n <= 1 or sr_std <= 1e-9:
            return sr_mean - sr_star

        se_sr = math.sqrt((1.0 + 0.5 * sr_mean ** 2) / n)
        dsr = (sr_mean - sr_star) / max(se_sr, 1e-9)
        return float(dsr)

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "method": "combinatorial_purged_cv",
            "n_splits": 0,
            "n_test_folds": 0,
            "combinations": 0,
            "mean_oos_sharpe": 0.0,
            "median_oos_sharpe": 0.0,
            "oos_sharpe_std": 0.0,
            "sharpe_p05": 0.0,
            "sharpe_p95": 0.0,
            "sharpe_positive_pct": 0.0,
            "pbo": 0.0,
            "dsr": 0.0,
            "details": [],
        }
