"""ADR-0055 commission stamp and fill-vs-reference slippage (S2, D3).

Commission is Free-plan all-in × contracts. Slippage lives in the fill price
and is reported in ticks and dollars when a reference price is supplied.
A missing reference omits slippage (does not invent 0.0 as a measurement).
Unknown roots are refused. This module never places an order.
"""

from __future__ import annotations

import math
from typing import Literal

from lumina_core.market.nt_fees import CostCardError, all_in_per_side_usd, spec_for

Direction = Literal["BUY", "SELL"]

COMMISSION_SOURCE: str = "adr0055_free"
EPS: float = 1e-12


class FillStampRefused(ValueError):
    """Commission or slippage cannot be stamped without inventing a number."""


def stamp_commission(symbol: str, qty: int) -> tuple[float, float, float]:
    """Return ``(commission_usd, commission_ticks, tick_value_usd)``.

    Free-plan all-in only. A zero commission is refused (the card is never free).
    """
    if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
        raise FillStampRefused("qty_invalid")
    try:
        commission_usd = float(all_in_per_side_usd(symbol, plan="free", qty=qty))
        quote = spec_for(symbol)
    except CostCardError as exc:
        raise FillStampRefused(f"root_not_on_card:{symbol}") from exc
    tick_size = float(quote.tick_size)
    tick_value_usd = float(quote.point_value_usd) * tick_size
    if tick_size <= 0.0 or tick_value_usd <= 0.0:
        raise FillStampRefused("tick_value_invalid")
    if not math.isfinite(commission_usd) or commission_usd <= 0.0:
        raise FillStampRefused("commission_zero")
    return commission_usd, commission_usd / tick_value_usd, tick_value_usd


def execution_commission(symbol: str, qty: int, claimed: float | None) -> tuple[float, float, bool]:
    """Card wins. ``claimed`` is recorded only to flag a discrepancy."""
    card_usd, card_ticks, _tick_usd = stamp_commission(symbol, qty)
    if claimed is None:
        return card_usd, card_ticks, False
    if not math.isfinite(float(claimed)):
        raise FillStampRefused("claimed_commission_non_finite")
    discrepancy = abs(float(claimed) - card_usd) > EPS
    return card_usd, card_ticks, discrepancy


def stamp_slippage(
    *,
    symbol: str,
    side: str,
    fill_price: float,
    reference_price: float | None,
    qty: int,
) -> tuple[float, float] | None:
    """Adverse ticks and dollars, or ``None`` when reference is omitted.

    BUY: fill above reference is adverse. SELL: fill below reference is adverse.
    """
    if reference_price is None:
        return None
    if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
        raise FillStampRefused("qty_invalid")
    if not math.isfinite(float(reference_price)) or float(reference_price) <= 0.0:
        raise FillStampRefused("reference_price_invalid")
    if not math.isfinite(float(fill_price)) or float(fill_price) <= 0.0:
        raise FillStampRefused("fill_price_invalid")
    action = str(side or "").strip().upper()
    if action not in {"BUY", "SELL"}:
        raise FillStampRefused("side_invalid")
    try:
        quote = spec_for(symbol)
    except CostCardError as exc:
        raise FillStampRefused(f"root_not_on_card:{symbol}") from exc
    tick_size = float(quote.tick_size)
    tick_value_usd = float(quote.point_value_usd) * tick_size
    if tick_size <= 0.0 or tick_value_usd <= 0.0:
        raise FillStampRefused("tick_value_invalid")
    delta = (float(fill_price) - float(reference_price)) / tick_size
    if action == "SELL":
        delta = -delta
    usd = float(delta) * tick_value_usd * float(qty)
    return float(delta), usd
