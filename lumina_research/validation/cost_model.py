"""Four-leg research cost model: commission + half-spread + slippage + sqrt impact.

Always applied. The Validation Gate refuses results without this provenance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from lumina_research.validation.contracts import ContractSpec, spec_for
from lumina_research.validation.types import CostProvenance

COST_MODEL_ID = "lumina_research.validation.cost_model"
COST_MODEL_VERSION = "1.0.0"
COST_COMPONENTS: tuple[str, ...] = ("commission", "half_spread", "slippage", "market_impact")


class CostModelError(ValueError):
    """Cost model refused to stamp provenance."""


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Volume and volatility for one bar / fill. Synthetic in tests; no downloads."""

    volume: float
    average_volume: float
    volatility_price: float


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    commission_ticks: float
    half_spread_ticks: float
    slippage_ticks: float
    impact_ticks: float
    total_ticks: float
    total_usd: float
    provenance: CostProvenance


@dataclass(frozen=True, slots=True)
class CostedSeries:
    net_returns: tuple[float, ...]
    gross_returns: tuple[float, ...]
    costs_usd: tuple[float, ...]
    provenance: CostProvenance


@dataclass(frozen=True, slots=True)
class CostModel:
    slippage_coefficient: float = 0.10
    impact_coefficient: float = 0.10

    def __post_init__(self) -> None:
        if self.slippage_coefficient < 0.0 or self.impact_coefficient < 0.0:
            raise CostModelError("slippage and impact coefficients must be >= 0")

    def ticks_for_fill(
        self,
        *,
        spec: ContractSpec,
        quantity: float,
        market: MarketSnapshot,
    ) -> CostBreakdown:
        if quantity <= 0.0:
            raise CostModelError("quantity must be positive")
        if market.average_volume <= 0.0 or market.volume < 0.0:
            raise CostModelError("volume must be non-negative and average_volume > 0")
        if market.volatility_price < 0.0:
            raise CostModelError("volatility must be >= 0")
        volatility_ticks = market.volatility_price / spec.tick_size
        volume_ratio = market.volume / market.average_volume if market.average_volume > 0.0 else 0.0
        slip_scale = 1.0 / max(volume_ratio, 1e-6)
        slippage = self.slippage_coefficient * volatility_ticks * slip_scale
        participation = abs(quantity) / max(market.average_volume, 1e-12)
        impact = self.impact_coefficient * volatility_ticks * math.sqrt(participation)
        total = spec.commission_ticks + spec.half_spread_ticks + slippage + impact
        provenance = _provenance(spec)
        return CostBreakdown(
            commission_ticks=spec.commission_ticks,
            half_spread_ticks=spec.half_spread_ticks,
            slippage_ticks=float(slippage),
            impact_ticks=float(impact),
            total_ticks=float(total),
            total_usd=float(total * spec.tick_value_usd * abs(quantity)),
            provenance=provenance,
        )


def apply_costs(
    *,
    gross_returns: Sequence[float],
    positions: Sequence[float],
    equity: float,
    spec: ContractSpec | str,
    markets: Sequence[MarketSnapshot],
    model: CostModel | None = None,
) -> CostedSeries:
    """Subtract four-leg costs on position changes. Stamps provenance always."""
    contract = spec if isinstance(spec, ContractSpec) else spec_for(spec)
    engine = model if model is not None else CostModel()
    n = len(gross_returns)
    if n == 0 or n != len(positions) or n != len(markets):
        raise CostModelError("gross_returns, positions and markets must be same non-zero length")
    if equity <= 0.0:
        raise CostModelError("equity must be positive")
    net: list[float] = []
    costs: list[float] = []
    previous = 0.0
    provenance = _provenance(contract)
    for index in range(n):
        position = float(positions[index])
        traded = abs(position - previous)
        cost_usd = 0.0
        if traded > 0.0:
            breakdown = engine.ticks_for_fill(spec=contract, quantity=traded, market=markets[index])
            cost_usd = breakdown.total_usd
            provenance = breakdown.provenance
        net.append(float(gross_returns[index]) - cost_usd / equity)
        costs.append(cost_usd)
        previous = position
    if not provenance.applied:
        raise CostModelError("cost provenance missing after apply_costs")
    return CostedSeries(
        net_returns=tuple(net),
        gross_returns=tuple(float(item) for item in gross_returns),
        costs_usd=tuple(costs),
        provenance=provenance,
    )


def _provenance(spec: ContractSpec) -> CostProvenance:
    return CostProvenance(
        model_id=COST_MODEL_ID,
        model_version=COST_MODEL_VERSION,
        components=COST_COMPONENTS,
        applied=True,
        contract_root=spec.root,
        tick_size=spec.tick_size,
        tick_value_usd=spec.tick_value_usd,
        commission_ticks=spec.commission_ticks,
    )
