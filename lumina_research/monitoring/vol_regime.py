"""Classify normal vs high-vol for FAR accounting. Does not change gate floors."""

from __future__ import annotations

import math
import statistics
from typing import Sequence

from lumina_research.monitoring.acceptance import (
    HIGH_VOL_REALIZED_MULT,
    HIGH_VOL_REALIZED_WINDOW,
    HIGH_VOL_TRAILING_PCT,
    HIGH_VOL_TRAILING_WINDOW,
    HIGH_VOL_VIX,
)
from lumina_research.monitoring.types import ContinuityRefused, Instrument, VolRegime

_ES_FAMILY: frozenset[str] = frozenset({"ES", "NQ"})


def realized_vol(values: Sequence[float], *, window: int = HIGH_VOL_REALIZED_WINDOW) -> float | None:
    """Population stdev of the last ``window`` observations. None if too short."""
    if window < 2:
        raise ContinuityRefused("realized-vol window must be >= 2")
    if len(values) < window:
        return None
    chunk = tuple(float(item) for item in values[-window:])
    if any(not math.isfinite(item) for item in chunk):
        raise ContinuityRefused("non-finite realized-vol observation")
    return float(statistics.pstdev(chunk))


def trailing_percentile(sample: Sequence[float], *, pct: float) -> float | None:
    """Empirical percentile of a trailing distribution. None if empty."""
    if pct < 0.0 or pct > 1.0:
        raise ContinuityRefused("percentile must be in [0, 1]")
    cleaned = tuple(float(item) for item in sample if math.isfinite(float(item)))
    if not cleaned:
        return None
    ordered = tuple(sorted(cleaned))
    index = min(len(ordered) - 1, max(0, int(pct * (len(ordered) - 1))))
    return float(ordered[index])


def classify_vol_regime(
    series: Sequence[float],
    *,
    vix: float | None = None,
    instrument: Instrument | str | None = None,
    realized_window: int = HIGH_VOL_REALIZED_WINDOW,
    trailing_window: int = HIGH_VOL_TRAILING_WINDOW,
) -> VolRegime:
    """High vol if 20d realized > trailing 75th pct, VIX>25, or ES/NQ 20d > 1.5x median.

    Insufficient history is classified ``normal`` (FAR uses the stricter 5% bucket until
    the instrument's own trailing distribution exists). That is fail-closed for the cap.
    """
    if vix is not None:
        if not math.isfinite(vix) or vix < 0.0:
            raise ContinuityRefused("VIX must be a finite number >= 0")
        if vix > HIGH_VOL_VIX:
            return "high_vol"
    current = realized_vol(series, window=realized_window)
    if current is None:
        return "normal"
    history = _trailing_realized(series, realized_window=realized_window, trailing_window=trailing_window)
    cap = trailing_percentile(history, pct=HIGH_VOL_TRAILING_PCT)
    if cap is not None and current > cap:
        return "high_vol"
    root = None if instrument is None else str(instrument).strip().upper()
    if root in _ES_FAMILY:
        median = trailing_percentile(history, pct=0.50)
        if median is not None and current > HIGH_VOL_REALIZED_MULT * median:
            return "high_vol"
    return "normal"


def _trailing_realized(
    series: Sequence[float],
    *,
    realized_window: int,
    trailing_window: int,
) -> tuple[float, ...]:
    if trailing_window < 2:
        raise ContinuityRefused("trailing window must be >= 2")
    vols: list[float] = []
    end = len(series) - 1
    start = realized_window
    floor = max(start, end - trailing_window + 1)
    for index in range(floor, end + 1):
        chunk = tuple(float(item) for item in series[: index + 1])
        vol = realized_vol(chunk, window=realized_window)
        if vol is not None:
            vols.append(vol)
    return tuple(vols)
