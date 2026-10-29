"""Volatility and trend regime robustness on MARKET regimes, not strategy PnL.

Researchers (D12): split on instrument realized vol and trend (or the existing
quiet-mask). Strategy Sharpe is then measured inside those market buckets.
"""

from __future__ import annotations

import math
import statistics
from typing import Sequence

from lumina_research.validation.metrics import annualized_sharpe
from lumina_research.validation.types import RegimeSnapshot


def regime_robustness(
    returns: Sequence[float],
    *,
    market_returns: Sequence[float] | None = None,
    periods_per_year: float = 252.0,
    vol_window: int = 20,
    trend_window: int = 20,
) -> RegimeSnapshot:
    series = tuple(float(item) for item in returns)
    n = len(series)
    if market_returns is None:
        return RegimeSnapshot.missing()
    if n < max(vol_window, trend_window) + 2:
        return RegimeSnapshot.missing()
    labels = tuple(float(item) for item in market_returns)
    if len(labels) != n:
        return RegimeSnapshot.missing()
    vol = _rolling_vol(labels, vol_window)
    trend = _rolling_trend(labels, trend_window)
    finite_vol = tuple(item for item in vol if math.isfinite(item))
    if len(finite_vol) < 2:
        return RegimeSnapshot.missing()
    median_vol = statistics.median(finite_vol)
    high_vol = tuple(series[i] for i in range(n) if vol[i] >= median_vol and math.isfinite(vol[i]))
    low_vol = tuple(series[i] for i in range(n) if vol[i] < median_vol and math.isfinite(vol[i]))
    up = tuple(series[i] for i in range(n) if trend[i] > 0.0)
    down = tuple(series[i] for i in range(n) if trend[i] <= 0.0)
    vol_high = _finite_regime_sharpe(annualized_sharpe(high_vol, periods_per_year=periods_per_year))
    vol_low = _finite_regime_sharpe(annualized_sharpe(low_vol, periods_per_year=periods_per_year))
    trend_up = _finite_regime_sharpe(annualized_sharpe(up, periods_per_year=periods_per_year))
    trend_down = _finite_regime_sharpe(annualized_sharpe(down, periods_per_year=periods_per_year))
    parts = (vol_high, vol_low, trend_up, trend_down)
    finite = tuple(part for part in parts if math.isfinite(part))
    if len(finite) < 4:
        robustness = math.nan
    else:
        positive = sum(1.0 for part in finite if part > 0.0)
        worst = min(finite)
        robustness = 0.5 * (positive / 4.0) + 0.5 * _squash(worst)
    return RegimeSnapshot(
        vol_high_sharpe=vol_high,
        vol_low_sharpe=vol_low,
        trend_up_sharpe=trend_up,
        trend_down_sharpe=trend_down,
        robustness=robustness,
    )


def _rolling_vol(series: Sequence[float], window: int) -> tuple[float, ...]:
    out: list[float] = []
    for index in range(len(series)):
        start = max(0, index - window + 1)
        chunk = series[start : index + 1]
        if len(chunk) < 2:
            out.append(math.nan)
        else:
            out.append(float(statistics.stdev(chunk)))
    return tuple(out)


def _rolling_trend(series: Sequence[float], window: int) -> tuple[float, ...]:
    out: list[float] = []
    for index in range(len(series)):
        start = max(0, index - window + 1)
        out.append(float(sum(series[start : index + 1])))
    return tuple(out)


def _finite_regime_sharpe(value: float) -> float:
    """Keep regime snapshots complete when a bucket has zero variance.

    Constant-loss strategy PnL inside a market bucket used to yield -inf and
    then ``missing_regimes``. Researchers (D12): labels come from the market;
    strategy Sharpe inside the bucket may be negative, but it must be defined.
    Empty buckets stay NaN (fail-closed).
    """
    if math.isfinite(value):
        return value
    if math.isinf(value):
        return 10.0 if value > 0.0 else -10.0
    return math.nan


def _squash(sharpe: float) -> float:
    return 1.0 / (1.0 + math.exp(-sharpe))
