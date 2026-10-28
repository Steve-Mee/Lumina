"""Volatility and trend regime robustness on OOS (net of costs) returns."""

from __future__ import annotations

import math
import statistics
from typing import Sequence

from lumina_research.validation.metrics import annualized_sharpe
from lumina_research.validation.types import RegimeSnapshot


def regime_robustness(
    returns: Sequence[float],
    *,
    periods_per_year: float = 252.0,
    vol_window: int = 20,
    trend_window: int = 20,
) -> RegimeSnapshot:
    series = tuple(float(item) for item in returns)
    n = len(series)
    if n < max(vol_window, trend_window) + 2:
        return RegimeSnapshot.missing()
    vol = _rolling_vol(series, vol_window)
    trend = _rolling_trend(series, trend_window)
    median_vol = statistics.median(vol)
    high_vol = tuple(series[i] for i in range(n) if vol[i] >= median_vol and math.isfinite(vol[i]))
    low_vol = tuple(series[i] for i in range(n) if vol[i] < median_vol and math.isfinite(vol[i]))
    up = tuple(series[i] for i in range(n) if trend[i] > 0.0)
    down = tuple(series[i] for i in range(n) if trend[i] <= 0.0)
    vol_high = annualized_sharpe(high_vol, periods_per_year=periods_per_year)
    vol_low = annualized_sharpe(low_vol, periods_per_year=periods_per_year)
    trend_up = annualized_sharpe(up, periods_per_year=periods_per_year)
    trend_down = annualized_sharpe(down, periods_per_year=periods_per_year)
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


def _squash(sharpe: float) -> float:
    return 1.0 / (1.0 + math.exp(-sharpe))
