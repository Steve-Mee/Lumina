"""Live-signal snapshots and stage ranks. Weights only fall."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal, Mapping, Sequence, assert_never

from lumina_core.agent_orchestration.schemas_research import SignalStage
from lumina_research.risk_core.types import cluster_for

Instrument = Literal["ES", "NQ", "MES", "MNQ"]

INSTRUMENT_FAMILIES: Mapping[str, str] = {
    "ES": "es_index",
    "MES": "es_index",
    "NQ": "nq_index",
    "MNQ": "nq_index",
}


class ContinuityRefused(ValueError):
    """Monitoring tried to increase exposure, skip the gate, or mutate Risk Core."""


# Percentile/z-tests need a real OOS sample. CPCV path counts may be below the WF floor of 6.
MIN_LIVE_OOS_VALUES = 4


def family_for(instrument: str) -> str:
    key = instrument.strip().upper()
    family = INSTRUMENT_FAMILIES.get(key)
    if family is None:
        raise ContinuityRefused(f"unknown instrument {instrument!r}")
    return family


def stage_rank(stage: SignalStage) -> int:
    if stage == "active":
        return 0
    if stage == "deweighted":
        return 1
    if stage == "suspended":
        return 2
    if stage == "retired":
        return 3
    assert_never(stage)


def stage_from_rank(rank: int) -> SignalStage:
    if rank <= 0:
        return "active"
    if rank == 1:
        return "deweighted"
    if rank == 2:
        return "suspended"
    return "retired"


def stage_weight(stage: SignalStage, *, deweight_multiplier: float) -> float:
    if stage == "active":
        return 1.0
    if stage == "deweighted":
        return float(deweight_multiplier)
    if stage == "suspended":
        return 0.0
    if stage == "retired":
        return 0.0
    assert_never(stage)


def tighter_stage(current: SignalStage, proposed: SignalStage) -> SignalStage:
    if stage_rank(proposed) > stage_rank(current):
        return proposed
    return current


@dataclass(frozen=True, slots=True)
class LiveSignal:
    signal_id: str
    hypothesis_id: str
    config_id: str
    trial_id: int
    instrument: Instrument
    family_id: str
    cluster_id: str
    stage: SignalStage
    weight: float
    capacity_scale: float
    base_quantity: float
    base_price: float
    base_notional: float
    oos_values: tuple[float, ...]
    oos_mean: float
    oos_stdev: float
    n_oos_windows: int
    median_oos_after_costs: float
    pbo: float
    dsr_probability: float
    purge_applied: bool
    embargo_applied: bool
    cost_applied: bool
    cost_model_id: str
    regimes_complete: bool
    validation_mac: str
    issue_mac: str
    report_sha256: str
    admission_mac: str
    state_mac: str

    def __init_subclass__(cls) -> None:
        raise TypeError("LiveSignal cannot be subclassed")

    def effective_notional(self) -> float:
        return float(self.base_notional) * float(self.weight) * float(self.capacity_scale)


@dataclass(frozen=True, slots=True)
class LiveObservation:
    signal_id: str
    day_index: int
    metric: float


@dataclass(frozen=True, slots=True)
class DecayAssessment:
    method: str
    severity: int
    stage: SignalStage
    statistic: float
    threshold: float
    live_mean: float | None
    oos_mean: float | None
    oos_stdev: float | None
    percentile: float | None
    cusum: float | None
    sprt_llr: float | None
    window: int
    votes_deweight: int
    votes_suspend: int
    votes_retire: int
    ready: bool


def require_cluster(instrument: str) -> str:
    try:
        return cluster_for(instrument)
    except ValueError as exc:
        raise ContinuityRefused(str(exc)) from exc


def finite_series(values: Sequence[float]) -> tuple[float, ...]:
    cleaned = tuple(float(item) for item in values)
    if any(not math.isfinite(item) for item in cleaned):
        raise ContinuityRefused("non-finite live or OOS value")
    return cleaned
