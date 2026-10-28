"""Regime detection for sizing and throttling only. Never a hard strategy switch."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Literal, Sequence

from lumina_core.agent_orchestration.schemas_research import ParameterGenome

VolRegime = Literal["high", "low"]
TrendRegime = Literal["up", "down"]


class RegimePolicyError(ValueError):
    """Attempt to use regime detection as a strategy switch."""


@dataclass(frozen=True, slots=True)
class RegimeObservation:
    vol: VolRegime
    trend: TrendRegime


@dataclass(frozen=True, slots=True)
class RegimeAction:
    size_multiplier: float
    throttle: bool
    vol: VolRegime
    trend: TrendRegime


class RegimePolicy:
    """Maps volatility/trend to a size multiplier. There is no strategy_id."""

    def __init_subclass__(cls) -> None:
        raise TypeError("RegimePolicy cannot be subclassed into a strategy switch")

    def act(self, observation: RegimeObservation, **kwargs: object) -> RegimeAction:
        if kwargs:
            raise RegimePolicyError("regime detection cannot switch strategies")
        multiplier = 1.0
        throttle = False
        if observation.vol == "high":
            multiplier *= 0.5
            throttle = True
        elif observation.vol == "low":
            pass
        else:
            raise RegimePolicyError("unknown volatility regime")
        if observation.trend == "down":
            multiplier *= 0.75
            throttle = True
        elif observation.trend == "up":
            pass
        else:
            raise RegimePolicyError("unknown trend regime")
        if not math.isfinite(multiplier) or multiplier <= 0.0 or multiplier > 1.0:
            raise RegimePolicyError("throttle produced an illegal size multiplier")
        return RegimeAction(
            size_multiplier=float(multiplier),
            throttle=throttle,
            vol=observation.vol,
            trend=observation.trend,
        )

    def switch_strategy(self, observation: RegimeObservation, strategy_id: str) -> None:
        del observation, strategy_id
        raise RegimePolicyError("regime detection cannot switch strategies")


def detect_regime(
    returns: Sequence[float],
    *,
    vol_window: int = 20,
    trend_window: int = 20,
) -> RegimeObservation:
    series = tuple(float(item) for item in returns)
    n = len(series)
    if n < max(vol_window, trend_window) + 2:
        return RegimeObservation(vol="low", trend="up")
    vol = _rolling_vol(series, vol_window)
    finite_vol = tuple(item for item in vol if math.isfinite(item))
    median_vol = statistics.median(finite_vol) if finite_vol else 0.0
    last_vol = vol[-1] if math.isfinite(vol[-1]) else median_vol
    trend = float(sum(series[max(0, n - trend_window) : n]))
    vol_label: VolRegime = "high" if last_vol >= median_vol else "low"
    trend_label: TrendRegime = "up" if trend > 0.0 else "down"
    return RegimeObservation(vol=vol_label, trend=trend_label)


def throttled_quantity(genome: ParameterGenome, action: RegimeAction) -> float:
    quantity = float(genome.quantity) * float(action.size_multiplier)
    if not math.isfinite(quantity) or quantity <= 0.0:
        raise RegimePolicyError("throttle produced a non-positive quantity")
    return quantity


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
