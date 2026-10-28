"""Sharpe, skew, Pearson kurtosis. Per-period Sharpe is what DSR consumes."""

from __future__ import annotations

import math
import statistics
from typing import Sequence


def period_sharpe(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return math.nan
    mu = float(statistics.fmean(returns))
    sd = float(statistics.stdev(returns))
    if sd <= 1e-18:
        if abs(mu) <= 1e-18:
            return math.nan
        return math.copysign(math.inf, mu)
    return mu / sd


def annualized_sharpe(returns: Sequence[float], *, periods_per_year: float = 252.0) -> float:
    per_period = period_sharpe(returns)
    if not math.isfinite(per_period):
        return per_period
    if periods_per_year <= 0.0:
        return math.nan
    return per_period * math.sqrt(periods_per_year)


def pearson_moments(returns: Sequence[float]) -> tuple[float, float]:
    """Return (skew γ3, Pearson kurtosis γ4). Normal → (0, 3)."""
    n = len(returns)
    if n < 3:
        return math.nan, math.nan
    mu = float(statistics.fmean(returns))
    second = 0.0
    third = 0.0
    fourth = 0.0
    for item in returns:
        delta = float(item) - mu
        sq = delta * delta
        second += sq
        third += sq * delta
        fourth += sq * sq
    second /= float(n)
    third /= float(n)
    fourth /= float(n)
    if second <= 1e-18:
        return 0.0, 3.0
    skew = third / (second ** 1.5)
    kurtosis = fourth / (second * second)
    return float(skew), float(kurtosis)
