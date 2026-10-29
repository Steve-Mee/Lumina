"""Limit-order fill model. Conservative trade-through; no zero-slippage.

Touch-fill (low <= buy limit / high >= sell limit) is optimistic: the print can
touch the price without the resting order being queued ahead of the trade.
This module requires the bar to **trade through** the limit (strict inequality).
Slippage in CostModel is a separate queue/adverse-selection term, not a second
fill probability, so the two are not double-counted as fill chances.
"""

from __future__ import annotations

from lumina_research.cycles.data import ResearchBar

FILL_POLICY = "trade_through_strict"
TOUCH_FILL_POLICY = "touch_inclusive"


class FillRefused(ValueError):
    """Fill model refused a non-finite input."""


def traded_through(*, side: float, limit: float, bar: ResearchBar) -> bool:
    """True when the bar trades strictly through ``limit`` (not a mere touch)."""
    if side > 0.0:
        return bar.low < limit
    if side < 0.0:
        return bar.high > limit
    return False


def touch_fill(*, side: float, limit: float, bar: ResearchBar) -> bool:
    """Optimistic touch rule. Kept for documentation tests; not used to fill."""
    if side > 0.0:
        return bar.low <= limit
    if side < 0.0:
        return bar.high >= limit
    return False


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
    volume_ok = bar.volume >= average_volume * volume_multiple
    return traded_through(side=side, limit=limit, bar=bar) and volume_ok


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
    if not traded_through(side=side, limit=limit, bar=bar):
        return 0.0
    return min(1.0, bar.volume / average_volume)
