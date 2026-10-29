"""Limit-order fill model. No zero-slippage assumption. Not a Validation Gate change."""

from __future__ import annotations

from lumina_research.cycles.data import ResearchBar


class FillRefused(ValueError):
    """Fill model refused a non-finite input."""


def trade_through_fill(
    *,
    side: float,
    limit: float,
    bar: ResearchBar,
    average_volume: float,
    volume_multiple: float = 0.35,
) -> bool:
    """Fill a day-order limit only on trade-through plus a volume condition."""
    if side == 0.0:
        return False
    if average_volume <= 0.0:
        raise FillRefused("average_volume must be > 0")
    if volume_multiple < 0.0:
        raise FillRefused("volume_multiple must be >= 0")
    if side > 0.0:
        through = bar.low <= limit
    else:
        through = bar.high >= limit
    volume_ok = bar.volume >= average_volume * volume_multiple
    return through and volume_ok


def fill_probability(
    *,
    side: float,
    limit: float,
    bar: ResearchBar,
    average_volume: float,
) -> float:
    """Probabilistic fill rate: 0 if not traded through, else min(1, volume/ADV)."""
    if side == 0.0:
        return 0.0
    if average_volume <= 0.0:
        raise FillRefused("average_volume must be > 0")
    if side > 0.0:
        through = bar.low <= limit
    else:
        through = bar.high >= limit
    if not through:
        return 0.0
    return min(1.0, bar.volume / average_volume)
