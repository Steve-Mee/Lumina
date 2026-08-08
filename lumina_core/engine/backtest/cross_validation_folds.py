"""Fold helpers for combinatorial purged CV (global residual)."""
from __future__ import annotations

import math
import statistics
from typing import Any

class CombinatorialPurgedCVFoldsMixin:
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
        sr_star = risk_free_rate + sr_std * math.sqrt(max(0.0, 2.0 * math.log(n_combinations)))

        # Standard error of SR estimate.
        n = len(oos_sharpes)
        if n <= 1 or sr_std <= 1e-9:
            return sr_mean - sr_star

        se_sr = math.sqrt((1.0 + 0.5 * sr_mean**2) / n)
        dsr = (sr_mean - sr_star) / max(se_sr, 1e-9)
        return float(dsr)
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
