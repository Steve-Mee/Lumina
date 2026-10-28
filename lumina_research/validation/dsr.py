"""Deflated Sharpe Ratio — Bailey & López de Prado (2014).

DSR is the Probabilistic Sharpe Ratio evaluated at SR* = E[max SR | N trials].

    PSR(SR*) = Φ[ (SR̂ - SR*) √(T-1) / √(1 - γ3 SR̂ + (γ4-1)/4 SR̂²) ]

which is equivalent to Φ[ (SR̂ - SR*) / se(SR̂) ] with the non-normal se.

    SR0 = se(SR̂) * [ (1-γ) Φ^{-1}(1-1/N) + γ Φ^{-1}(1-1/(N e)) ]

under a null mean of 0. N comes exclusively from a TrialRegistry.
γ is the Euler-Mascheroni constant. γ3 is skewness, γ4 is Pearson kurtosis
(3 for a Normal). SR̂ is the *per-period* Sharpe (not annualized); T is the
number of periods.

Reference values used in tests are computed from these closed forms (z-table
and Euler-Mascheroni), not from a fitted backtest.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Sequence

from lumina_research.validation.metrics import pearson_moments, period_sharpe
from lumina_research.validation.trial_registry import TrialRegistry
from lumina_research.validation.types import DSRSnapshot

EULER_MASCHERONI = 0.5772156649015328606
DSR_FORMULATION = "bailey_lopez_de_prado_2014"
_NORM = NormalDist()


class DSRError(ValueError):
    """DSR cannot be computed from the supplied inputs."""


def expected_max_sharpe(*, n_trials: int, sr_std: float, sr_mean: float = 0.0) -> float:
    """E[max SR] under N independent trials (Bailey & López de Prado 2014)."""
    if n_trials < 1:
        raise DSRError("n_trials must come from the registry and be >= 1")
    if sr_std < 0.0 or not math.isfinite(sr_std):
        raise DSRError("sr_std must be a finite non-negative number")
    if n_trials == 1:
        return sr_mean
    z_hi = _NORM.inv_cdf(1.0 - 1.0 / float(n_trials))
    z_lo = _NORM.inv_cdf(1.0 - 1.0 / (float(n_trials) * math.e))
    scale = (1.0 - EULER_MASCHERONI) * z_hi + EULER_MASCHERONI * z_lo
    return sr_mean + sr_std * scale


def sharpe_standard_error(*, sr: float, n_observations: int, skew: float, kurtosis: float) -> float:
    """Non-normal standard error of SR̂. Lo (2002) / Bailey & López de Prado (2014)."""
    if n_observations < 2:
        raise DSRError("DSR requires at least 2 observations")
    if not math.isfinite(sr) or not math.isfinite(skew) or not math.isfinite(kurtosis):
        raise DSRError("SR, skew and kurtosis must be finite")
    variance = (1.0 - skew * sr + ((kurtosis - 1.0) / 4.0) * sr * sr) / float(n_observations - 1)
    if not math.isfinite(variance) or variance <= 0.0:
        raise DSRError("SR variance is non-positive; DSR is undefined")
    return math.sqrt(variance)


def probabilistic_sharpe_ratio(
    *,
    sr: float,
    sr_star: float,
    n_observations: int,
    skew: float,
    kurtosis: float,
) -> float:
    se = sharpe_standard_error(sr=sr, n_observations=n_observations, skew=skew, kurtosis=kurtosis)
    return float(_NORM.cdf((sr - sr_star) / se))


def deflated_sharpe_from_moments(
    *,
    sr: float,
    n_observations: int,
    skew: float,
    kurtosis: float,
    registry: TrialRegistry,
) -> DSRSnapshot:
    n_trials = registry.n_trials
    if n_trials < 1:
        raise DSRError("trial registry is empty; DSR refuses an uncounted trial")
    se = sharpe_standard_error(sr=sr, n_observations=n_observations, skew=skew, kurtosis=kurtosis)
    expected = expected_max_sharpe(n_trials=n_trials, sr_std=se, sr_mean=0.0)
    probability = probabilistic_sharpe_ratio(
        sr=sr,
        sr_star=expected,
        n_observations=n_observations,
        skew=skew,
        kurtosis=kurtosis,
    )
    return DSRSnapshot(
        probability=float(probability),
        observed_sr=float(sr),
        expected_max_sr=float(expected),
        sr_standard_error=float(se),
        n_trials=n_trials,
        n_observations=n_observations,
        skew=float(skew),
        kurtosis=float(kurtosis),
        formulation=DSR_FORMULATION,
    )


def deflated_sharpe_ratio(
    returns: Sequence[float],
    *,
    registry: TrialRegistry,
    **kwargs: object,
) -> DSRSnapshot:
    if kwargs:
        raise TypeError("n_trials cannot be passed in; it comes from the trial registry")
    series = tuple(float(item) for item in returns)
    if len(series) < 3:
        raise DSRError("DSR requires at least 3 returns (skew/kurtosis)")
    sr = period_sharpe(series)
    skew, kurtosis = pearson_moments(series)
    return deflated_sharpe_from_moments(
        sr=sr,
        n_observations=len(series),
        skew=skew,
        kurtosis=kurtosis,
        registry=registry,
    )
