"""Hypothetical SHADOW fills: ADR-0055 commission; slippage in the fill price (D3)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from lumina_core.market.nt_fees import all_in_per_side_usd, spec_for
from lumina_research.validation.contracts import spec_for as research_spec_for
from lumina_research.validation.cost_model import CostModel, MarketSnapshot

Direction = Literal["BUY", "SELL"]
InstrumentRoot = Literal["ES", "NQ", "MES", "MNQ"]


@dataclass(frozen=True, slots=True)
class ExecutionSideCosts:
    """Execution-side numbers. FillEvent SSOT. Research four-leg is recorded beside."""

    fill_price: float
    reference_price: float
    commission_usd: float
    commission_ticks: float
    slippage_ticks: float
    slippage_usd: float
    tick_size: float
    tick_value_usd: float
    research_total_usd: float | None
    discrepancy: bool


def tick_value_usd(instrument: str) -> float:
    quote = spec_for(instrument)
    return float(quote.point_value_usd) * float(quote.tick_size)


def hypothetical_execution_costs(
    *,
    instrument: InstrumentRoot,
    direction: Direction,
    size: float,
    reference_price: float,
    qty: int | None = None,
) -> ExecutionSideCosts:
    """One-tick adverse fill. Commission is Free-plan all-in × contracts. No extra cash tick."""
    if not math.isfinite(reference_price) or reference_price <= 0.0:
        raise ValueError("reference_price must be a finite number > 0")
    if not math.isfinite(size) or size <= 0.0:
        raise ValueError("size must be a finite number > 0")
    if qty is not None:
        contracts = int(qty)
    else:
        truncated = int(size)
        contracts = truncated if truncated >= 1 else 1
    if contracts < 1:
        raise ValueError("quantity must be >= 1 contract")
    quote = spec_for(instrument)
    tick_size = float(quote.tick_size)
    tick_usd = float(quote.point_value_usd) * tick_size
    if direction == "BUY":
        fill_price = float(reference_price) + tick_size
    else:
        fill_price = float(reference_price) - tick_size
    slip_ticks = abs(fill_price - float(reference_price)) / tick_size
    slip_usd = float(slip_ticks) * tick_usd * float(contracts)
    commission_usd = float(all_in_per_side_usd(instrument, qty=contracts))
    commission_ticks = commission_usd / tick_usd if tick_usd > 0.0 else 0.0
    research_total = _research_four_leg_usd(instrument=instrument, quantity=float(contracts), tick_size=tick_size)
    execution_total = commission_usd + slip_usd
    discrepancy = research_total is not None and float(research_total) > execution_total + 1e-12
    return ExecutionSideCosts(
        fill_price=fill_price,
        reference_price=float(reference_price),
        commission_usd=commission_usd,
        commission_ticks=float(commission_ticks),
        slippage_ticks=float(slip_ticks),
        slippage_usd=float(slip_usd),
        tick_size=tick_size,
        tick_value_usd=tick_usd,
        research_total_usd=research_total,
        discrepancy=bool(discrepancy),
    )


def _research_four_leg_usd(*, instrument: InstrumentRoot, quantity: float, tick_size: float) -> float | None:
    spec = research_spec_for(instrument)
    market = MarketSnapshot(volume=1_000.0, average_volume=1_000.0, volatility_price=tick_size * 4.0)
    breakdown = CostModel().ticks_for_fill(spec=spec, quantity=quantity, market=market)
    return float(breakdown.total_usd)
