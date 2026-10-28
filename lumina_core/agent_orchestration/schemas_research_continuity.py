"""Phase 4 continuity Event Bus payloads. Re-exported from ``schemas_research``."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RESEARCH_DECAY_TOPIC = "research.decay.detected"
RESEARCH_DEWEIGHT_TOPIC = "research.signal.deweighted"
RESEARCH_SUSPEND_TOPIC = "research.signal.suspended"
RESEARCH_RETIRE_TOPIC = "research.signal.retired"
RESEARCH_CAPACITY_TOPIC = "research.capacity.scaled"
RESEARCH_GUARDIAN_TOPIC = "research.guardian.finding"
RESEARCH_REPLENISH_TOPIC = "research.replenishment.requested"

MONITOR_AGENT_ID = "live_monitor_agent"
CAPACITY_AGENT_ID = "capacity_agent"
GUARDIAN_AGENT_ID = "guardian_agent"
REPLENISH_AGENT_ID = "replenish_agent"

DECAY_SCHEMA_VERSION: Literal["research.decay.detected.v1"] = "research.decay.detected.v1"
DEWEIGHT_SCHEMA_VERSION: Literal["research.signal.deweighted.v1"] = "research.signal.deweighted.v1"
SUSPEND_SCHEMA_VERSION: Literal["research.signal.suspended.v1"] = "research.signal.suspended.v1"
RETIRE_SCHEMA_VERSION: Literal["research.signal.retired.v1"] = "research.signal.retired.v1"
CAPACITY_SCHEMA_VERSION: Literal["research.capacity.scaled.v1"] = "research.capacity.scaled.v1"
GUARDIAN_SCHEMA_VERSION: Literal["research.guardian.finding.v1"] = "research.guardian.finding.v1"
REPLENISH_SCHEMA_VERSION: Literal["research.replenishment.requested.v1"] = "research.replenishment.requested.v1"

SignalStage = Literal["active", "deweighted", "suspended", "retired"]
DecayMethod = Literal["ztest", "percentile", "cusum", "sprt", "combined"]
GuardianCadence = Literal["daily", "weekly"]
GuardianSeverity = Literal["ok", "warn", "violation"]
ReplenishReason = Literal["active_count", "capacity"]

CONTINUITY_TOPIC_PRODUCERS: dict[str, frozenset[str]] = {
    RESEARCH_DECAY_TOPIC: frozenset({MONITOR_AGENT_ID}),
    RESEARCH_DEWEIGHT_TOPIC: frozenset({MONITOR_AGENT_ID}),
    RESEARCH_SUSPEND_TOPIC: frozenset({MONITOR_AGENT_ID}),
    RESEARCH_RETIRE_TOPIC: frozenset({MONITOR_AGENT_ID}),
    RESEARCH_CAPACITY_TOPIC: frozenset({CAPACITY_AGENT_ID}),
    RESEARCH_GUARDIAN_TOPIC: frozenset({GUARDIAN_AGENT_ID}),
    RESEARCH_REPLENISH_TOPIC: frozenset({REPLENISH_AGENT_ID}),
}

CONTINUITY_GUARDED_TOPICS: frozenset[str] = frozenset(CONTINUITY_TOPIC_PRODUCERS)


class DecayDetected(BaseModel):
    """Live paper/shadow metric has left the promotion-time OOS distribution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.decay.detected.v1"] = DECAY_SCHEMA_VERSION
    signal_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    method: DecayMethod
    statistic: float
    threshold: float
    window: int = Field(ge=1)
    live_mean: float | None
    oos_mean: float | None
    oos_stdev: float | None
    percentile: float | None
    cusum: float | None
    sprt_llr: float | None
    stage: SignalStage
    vol_regime: Literal["normal", "high_vol"] = "normal"
    horizon: Literal["short", "medium"] = "short"
    provenance_mac: str = Field(min_length=64, max_length=64)


class SignalDeweighted(BaseModel):
    """First staged reduction. ``new_weight`` is strictly below ``previous_weight``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.signal.deweighted.v1"] = DEWEIGHT_SCHEMA_VERSION
    signal_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    previous_weight: float = Field(ge=0.0, le=1.0)
    new_weight: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    provenance_mac: str = Field(min_length=64, max_length=64)


class SignalSuspended(BaseModel):
    """Second staged reduction: no new exposure. Weight is zero."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.signal.suspended.v1"] = SUSPEND_SCHEMA_VERSION
    signal_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    previous_weight: float = Field(ge=0.0, le=1.0)
    new_weight: float = Field(ge=0.0, le=0.0)
    reason: str = Field(min_length=1)
    provenance_mac: str = Field(min_length=64, max_length=64)


class SignalRetired(BaseModel):
    """Final staged reduction. The signal cannot regain weight except via a new gated trial."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.signal.retired.v1"] = RETIRE_SCHEMA_VERSION
    signal_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    previous_weight: float = Field(ge=0.0, le=1.0)
    new_weight: float = Field(ge=0.0, le=0.0)
    reason: str = Field(min_length=1)
    provenance_mac: str = Field(min_length=64, max_length=64)


class CapacityScaled(BaseModel):
    """Over-concentration scale-back. ``new_scale`` is never above ``previous_scale``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.capacity.scaled.v1"] = CAPACITY_SCHEMA_VERSION
    signal_id: str = Field(min_length=1)
    instrument: Literal["ES", "NQ", "MES", "MNQ"]
    family_id: str = Field(min_length=1)
    cluster_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    previous_scale: float = Field(ge=0.0, le=1.0)
    new_scale: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...]
    provenance_mac: str = Field(min_length=64, max_length=64)


class GuardianEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = Field(min_length=1)
    observed: str
    required: str


class GuardianFinding(BaseModel):
    """Charter compliance finding. Violations may propose suspension only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.guardian.finding.v1"] = GUARDIAN_SCHEMA_VERSION
    finding_id: str = Field(min_length=1)
    cadence: GuardianCadence
    check_id: str = Field(min_length=1)
    signal_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    passed: bool
    severity: GuardianSeverity
    suspend_proposed: bool
    evidence: GuardianEvidence
    provenance_mac: str = Field(min_length=64, max_length=64)


class ReplenishmentRequested(BaseModel):
    """Request for new hypotheses. This event never admits a live signal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.replenishment.requested.v1"] = REPLENISH_SCHEMA_VERSION
    request_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    reason: ReplenishReason
    n_active: int = Field(ge=0)
    floor: float = Field(ge=0.0)
    n_requested: int = Field(ge=1)
    provenance_mac: str = Field(min_length=64, max_length=64)
