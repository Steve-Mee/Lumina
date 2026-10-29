"""Instrument-specific one-way cost bands in USD/contract and bp. Not gate floors.

Researchers (B4): a tick band is not realistic for MNQ because Free-plan
commission alone is $0.94 ≈ 1.88 MNQ ticks. Micros stay expensive in dollars.
Report $/contract (side and round-trip) and basis points vs reference notional.
Commission is ADR-0055 Free: MES/MNQ $0.94/side, ES/NQ $2.87/side.
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina_research.cycles.slippage_calibration import reference_market
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import CostModel

# Four-leg one-way USD/contract bands (commission + half-spread + slippage + impact).
ES_ONE_WAY_USD = (3.00, 12.00)
NQ_ONE_WAY_USD = (3.00, 12.00)
MES_ONE_WAY_USD = (1.50, 6.00)
MNQ_ONE_WAY_USD = (1.20, 5.00)
# Historical tick conversions of those USD bands. Not the MNQ/MES band (B4).
ES_NQ_ONE_WAY = (0.5, 1.5)
MES_MNQ_ONE_WAY = (1.0, 2.5)
REFERENCE_NOTIONAL_USD = {"ES": 250_000.0, "NQ": 80_000.0, "MES": 25_000.0, "MNQ": 8_000.0}
# ADR-0055 Free plan, per contract.
COMMISSION_USD_PER_SIDE = {"ES": 2.87, "NQ": 2.87, "MES": 0.94, "MNQ": 0.94}


@dataclass(frozen=True, slots=True)
class CostBand:
    root: str
    modeled_one_way_ticks: float
    modeled_one_way_usd: float
    modeled_one_way_bp: float
    band_min: float
    band_max: float
    band_min_usd: float
    band_max_usd: float
    in_band: bool
    note: str
    tick_value_usd: float
    commission_usd_per_contract_per_side: float
    commission_usd_round_trip: float
    half_spread_usd_per_contract: float
    modeled_eth_one_way_usd: float
    modeled_eth_one_way_bp: float


def band_for(root: str) -> tuple[float, float]:
    spec = spec_for(root)
    if spec.root == "ES":
        return ES_ONE_WAY_USD
    if spec.root == "NQ":
        return NQ_ONE_WAY_USD
    if spec.root == "MES":
        return MES_ONE_WAY_USD
    if spec.root == "MNQ":
        return MNQ_ONE_WAY_USD
    raise ValueError(f"no cost band for {root!r}")


def commission_usd_per_side(root: str) -> float:
    spec = spec_for(root)
    usd = COMMISSION_USD_PER_SIDE[spec.root]
    if abs(spec.commission_usd_per_side - usd) > 1e-9:
        raise ValueError(f"{spec.root} commission ticks do not match ADR-0055 ${usd:.2f}/side")
    return usd


def modeled_one_way_ticks(root: str, *, quantity: float = 1.0, session: str = "rth") -> float:
    spec = spec_for(root)
    model = CostModel()
    market = reference_market(spec, session=session)
    return float(model.ticks_for_fill(spec=spec, quantity=quantity, market=market).total_ticks)


def report_band(root: str) -> CostBand:
    spec = spec_for(root)
    lo, hi = band_for(root)
    ticks = modeled_one_way_ticks(root, session="rth")
    usd = ticks * spec.tick_value_usd
    notional = REFERENCE_NOTIONAL_USD[spec.root]
    bp = 10_000.0 * usd / notional
    eth_ticks = modeled_one_way_ticks(root, session="eth")
    eth_usd = eth_ticks * spec.tick_value_usd
    eth_bp = 10_000.0 * eth_usd / notional
    comm = commission_usd_per_side(root)
    inside = lo <= usd <= hi
    note = (
        "modeled RTH one-way USD/contract sits in the instrument-specific dollar band"
        if inside
        else (
            "modeled RTH one-way USD/contract sits outside the instrument-specific "
            "dollar band; CostModel coefficient is not retuned on holdout "
            "(see slippage_calibration)"
        )
    )
    return CostBand(
        root=spec.root,
        modeled_one_way_ticks=ticks,
        modeled_one_way_usd=usd,
        modeled_one_way_bp=bp,
        band_min=lo,
        band_max=hi,
        band_min_usd=lo,
        band_max_usd=hi,
        in_band=inside,
        note=note,
        tick_value_usd=spec.tick_value_usd,
        commission_usd_per_contract_per_side=comm,
        commission_usd_round_trip=2.0 * comm,
        half_spread_usd_per_contract=spec.half_spread_ticks * spec.tick_value_usd,
        modeled_eth_one_way_usd=eth_usd,
        modeled_eth_one_way_bp=eth_bp,
    )
