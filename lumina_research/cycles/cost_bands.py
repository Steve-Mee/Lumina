"""Steve P5 cost bands versus the existing four-leg CostModel. Bands are not gate floors."""

from __future__ import annotations

from dataclasses import dataclass

from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import CostModel, MarketSnapshot

# Average one-way ticks excluding a separate impact term, as briefed 2026-10-28.
ES_NQ_ONE_WAY = (0.5, 1.5)
MES_MNQ_ONE_WAY = (1.0, 2.5)


@dataclass(frozen=True, slots=True)
class CostBand:
    root: str
    modeled_one_way_ticks: float
    band_min: float
    band_max: float
    in_band: bool
    note: str


def band_for(root: str) -> tuple[float, float]:
    spec = spec_for(root)
    if spec.root in {"ES", "NQ"}:
        return ES_NQ_ONE_WAY
    if spec.root in {"MES", "MNQ"}:
        return MES_MNQ_ONE_WAY
    raise ValueError(f"no cost band for {root!r}")


def modeled_one_way_ticks(root: str, *, quantity: float = 1.0) -> float:
    spec = spec_for(root)
    model = CostModel()
    market = MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=2.0)
    return float(model.ticks_for_fill(spec=spec, quantity=quantity, market=market).total_ticks)


def report_band(root: str) -> CostBand:
    lo, hi = band_for(root)
    modeled = modeled_one_way_ticks(root)
    inside = lo <= modeled <= hi
    note = (
        "modeled ticks sit in the briefed average band"
        if inside
        else (
            "modeled ticks sit outside the briefed average band; "
            "CostModel is unchanged — calibrate on SIM fills, do not retune the gate"
        )
    )
    return CostBand(
        root=spec_for(root).root,
        modeled_one_way_ticks=modeled,
        band_min=lo,
        band_max=hi,
        in_band=inside,
        note=note,
    )
