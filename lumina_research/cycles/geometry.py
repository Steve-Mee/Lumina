"""Pre-registered trade geometry per contract. Not Validation Gate floors.

Researchers (2026-10-29): target/stop is a design choice per template/family,
pre-registered, never tuned on holdout. There is no fixed 16/8 tick floor.
``CATALOG_DEFAULT_GEOMETRY`` records what the first P2 cycle used.
"""

from __future__ import annotations

from dataclasses import dataclass

from lumina_research.cycles.slippage_calibration import reference_market
from lumina_research.validation.contracts import ContractSpec, spec_for
from lumina_research.validation.cost_model import CostModel

# Historical first-cycle defaults. Not enforced.
CATALOG_DEFAULT_GEOMETRY: dict[str, tuple[int, int]] = {
    "ES": (8, 4),
    "NQ": (8, 4),
    "MES": (16, 8),
    "MNQ": (16, 8),
}
TICK_FLOORS = CATALOG_DEFAULT_GEOMETRY


class GeometryRefused(ValueError):
    """Target or stop is non-positive, or the root has no catalog default."""


@dataclass(frozen=True, slots=True)
class Geometry:
    root: str
    target_ticks: int
    stop_ticks: int
    tick_size: float
    tick_value_usd: float
    roundtrip_cost_ticks: float
    net_target_ticks: float
    net_stop_ticks: float
    net_target_usd: float
    net_stop_usd: float
    break_even_win_rate: float


def floors_for(root: str) -> tuple[int, int]:
    spec = spec_for(root)
    pair = TICK_FLOORS.get(spec.root)
    if pair is None:
        raise GeometryRefused(f"no tick floors for {root!r}")
    return pair


def require_geometry(*, root: str, target_ticks: int, stop_ticks: int) -> Geometry:
    spec = spec_for(root)
    if int(target_ticks) < 1:
        raise GeometryRefused(f"{spec.root} target {target_ticks} must be >= 1 tick")
    if int(stop_ticks) < 1:
        raise GeometryRefused(f"{spec.root} stop {stop_ticks} must be >= 1 tick")
    cost = _roundtrip_ticks(spec)
    net_target = float(target_ticks) - cost
    net_stop = float(stop_ticks) + cost
    denom = net_target + net_stop
    be = 1.0 if denom <= 0.0 else net_stop / denom
    return Geometry(
        root=spec.root,
        target_ticks=int(target_ticks),
        stop_ticks=int(stop_ticks),
        tick_size=spec.tick_size,
        tick_value_usd=spec.tick_value_usd,
        roundtrip_cost_ticks=cost,
        net_target_ticks=net_target,
        net_stop_ticks=net_stop,
        net_target_usd=net_target * spec.tick_value_usd,
        net_stop_usd=net_stop * spec.tick_value_usd,
        break_even_win_rate=be,
    )


def _roundtrip_ticks(spec: ContractSpec) -> float:
    model = CostModel()
    fill = model.ticks_for_fill(spec=spec, quantity=1.0, market=reference_market(spec))
    return 2.0 * fill.total_ticks
