"""Instrument-specific one-way cost bands in USD (and bp). Not gate floors.

Researchers (B4): a tick band is not realistic for MNQ because commission alone
is $0.94 ≈ 1.88 MNQ ticks. Micros stay expensive; report dollars / basis points.
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina_research.cycles.slippage_calibration import reference_market
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import CostModel

# One-way USD bands (commission + half-spread + slippage + impact), instrument-specific.
ES_ONE_WAY_USD = (3.00, 12.00)
NQ_ONE_WAY_USD = (3.00, 12.00)
MES_ONE_WAY_USD = (1.50, 6.00)
MNQ_ONE_WAY_USD = (1.20, 5.00)
# Kept as informational tick conversions of the USD bands at the reference snapshot.
ES_NQ_ONE_WAY = (0.5, 1.5)
MES_MNQ_ONE_WAY = (1.0, 2.5)
REFERENCE_NOTIONAL_USD = {"ES": 250_000.0, "NQ": 80_000.0, "MES": 25_000.0, "MNQ": 8_000.0}


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


def modeled_one_way_ticks(root: str, *, quantity: float = 1.0) -> float:
    spec = spec_for(root)
    model = CostModel()
    market = reference_market(spec)
    return float(model.ticks_for_fill(spec=spec, quantity=quantity, market=market).total_ticks)


def report_band(root: str) -> CostBand:
    spec = spec_for(root)
    lo, hi = band_for(root)
    ticks = modeled_one_way_ticks(root)
    usd = ticks * spec.tick_value_usd
    notional = REFERENCE_NOTIONAL_USD[spec.root]
    bp = 10_000.0 * usd / notional
    inside = lo <= usd <= hi
    note = (
        "modeled one-way USD sits in the instrument-specific dollar band"
        if inside
        else (
            "modeled one-way USD sits outside the instrument-specific dollar band; "
            "CostModel coefficient is not retuned on holdout (see slippage_calibration)"
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
    )
