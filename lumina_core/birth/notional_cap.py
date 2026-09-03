"""Birth SIM exam notional SSOT — one cap for gym, plant, and guard.

Live stop PRICE may still be geometry. Booked exam PnL cannot be a $1M gap mark.

Birth gym fills settle at MES $5 (geometry SSOT) even when the certified tape
is labeled NQ. The $500 / 1%-of-equity clip is a GAP backstop, not the typical
close. Two living point-values (NQ $20 fills + MES $5 cap) made 73% of S5
closes sit on the cap — that split is forbidden.
"""

from __future__ import annotations

from lumina_core.birth.birth_trade_geometry import MES_POINT_VALUE_USD, MES_TICK_SIZE
from lumina_core.birth.foundation_metrics import S5_DD_EQUITY_USD

BIRTH_EXAM_RISK_FRAC = 0.01


def birth_gym_point_value() -> float:
    """Birth gym fill settlement. Geometry SSOT. Not the tape's NQ $20."""
    return float(MES_POINT_VALUE_USD)


def birth_fill_pnl_usd(
    *,
    entry_price: float,
    exit_price: float,
    side: int,
    quantity: int,
) -> float:
    """Gross fill dollars: Δprice × side × qty × MES $5."""
    qty = max(0, int(quantity))
    return float(
        (float(exit_price) - float(entry_price)) * int(side) * qty * birth_gym_point_value()
    )


def one_tick_usd(
    *,
    qty: int = 1,
    tick_size: float = MES_TICK_SIZE,
    point_value: float = MES_POINT_VALUE_USD,
) -> float:
    """Honest one-tick slippage in exam dollars (MES $5 × 0.25)."""
    return abs(float(tick_size)) * abs(float(point_value)) * float(max(1, int(qty)))


def birth_close_cap_usd(
    *,
    entry_price: float,
    qty: int,
    equity: float = S5_DD_EQUITY_USD,
) -> float:
    """Max booked |PnL| for one birth-SIM close (before the one-tick allowance).

    Birth ``force_qty_one`` ⇒ qty_n=1 ⇒ equity cap is $500 on the $50k yardstick.
    """
    qty_n = max(1, int(qty))
    price_cap = BIRTH_EXAM_RISK_FRAC * abs(float(entry_price)) * float(qty_n) * MES_POINT_VALUE_USD
    equity_cap = BIRTH_EXAM_RISK_FRAC * float(equity) * float(qty_n)
    return float(min(price_cap, equity_cap))


def birth_exam_book_limit_usd(
    *,
    entry_price: float,
    qty: int = 1,
    equity: float = S5_DD_EQUITY_USD,
) -> float:
    """Cap plus one honest tick. A unit test fails if a birth close books above this."""
    qty_n = max(1, int(qty))
    return birth_close_cap_usd(entry_price=entry_price, qty=qty_n, equity=equity) + one_tick_usd(
        qty=qty_n
    )


def clip_birth_exam_pnl(
    raw_usd: float,
    *,
    entry_price: float,
    qty: int = 1,
    equity: float = S5_DD_EQUITY_USD,
) -> float:
    """sign(raw) * min(|raw|, cap + one_tick). Does not invent a win from a loss."""
    raw = float(raw_usd)
    if raw == 0.0:
        return 0.0
    limit = birth_exam_book_limit_usd(entry_price=entry_price, qty=qty, equity=equity)
    mag = min(abs(raw), float(limit))
    return mag if raw > 0.0 else -mag


def birth_stop_pct_dollar_cap(
    *,
    price: float,
    qty: int = 1,
    equity: float = S5_DD_EQUITY_USD,
) -> float:
    """stop_pct so qty × stop × price × MES $5 ≤ 1% of exam equity. Qty is in the denominator."""
    qty_n = max(1, int(qty))
    px = abs(float(price))
    eq = max(0.0, float(equity))
    if px <= 0.0 or eq <= 0.0:
        return 0.0
    return (eq * BIRTH_EXAM_RISK_FRAC) / (px * MES_POINT_VALUE_USD * float(qty_n))


__all__ = [
    "BIRTH_EXAM_RISK_FRAC",
    "birth_close_cap_usd",
    "birth_exam_book_limit_usd",
    "birth_fill_pnl_usd",
    "birth_gym_point_value",
    "birth_stop_pct_dollar_cap",
    "clip_birth_exam_pnl",
    "one_tick_usd",
]
