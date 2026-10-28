"""Typed EventBus / Blackboard payload contracts for propose-only research.

Additive topics only. Existing Event Bus / Blackboard contracts stay unchanged.
Frozen, extra=forbid, versioned. Schema SSOT is imported from ``schemas``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESEARCH_HYPOTHESIS_TOPIC = "research.hypothesis.proposed"
RESEARCH_VALIDATION_TOPIC = "research.validation.result"
RESEARCH_PROMOTION_TOPIC = "research.promotion.candidate"
RESEARCH_MUTATION_TOPIC = "research.mutation.proposed"
RESEARCH_GOVERNANCE_TOPIC = "research.governance.decision"
RESEARCH_DECAY_TOPIC = "research.decay.detected"
RESEARCH_DEWEIGHT_TOPIC = "research.signal.deweighted"
RESEARCH_SUSPEND_TOPIC = "research.signal.suspended"
RESEARCH_RETIRE_TOPIC = "research.signal.retired"
RESEARCH_CAPACITY_TOPIC = "research.capacity.scaled"
RESEARCH_GUARDIAN_TOPIC = "research.guardian.finding"
RESEARCH_REPLENISH_TOPIC = "research.replenishment.requested"

HYPOTHESIS_AGENT_ID = "hypothesis_agent"
VALIDATION_AGENT_ID = "validation_agent"
PROMOTION_AGENT_ID = "promotion_agent"
REFLECTOR_AGENT_ID = "reflector_agent"
BIRTH_AGENT_ID = "birth_agent"
GOVERNANCE_AGENT_ID = "governance_agent"
MONITOR_AGENT_ID = "live_monitor_agent"
CAPACITY_AGENT_ID = "capacity_agent"
GUARDIAN_AGENT_ID = "guardian_agent"
REPLENISH_AGENT_ID = "replenish_agent"

HYPOTHESIS_SCHEMA_VERSION: Literal["research.hypothesis.proposed.v1"] = "research.hypothesis.proposed.v1"
VALIDATION_SCHEMA_VERSION: Literal["research.validation.result.v1"] = "research.validation.result.v1"
PROMOTION_SCHEMA_VERSION: Literal["research.promotion.candidate.v1"] = "research.promotion.candidate.v1"
MUTATION_SCHEMA_VERSION: Literal["research.mutation.proposed.v1"] = "research.mutation.proposed.v1"
GOVERNANCE_SCHEMA_VERSION: Literal["research.governance.decision.v1"] = "research.governance.decision.v1"
DECAY_SCHEMA_VERSION: Literal["research.decay.detected.v1"] = "research.decay.detected.v1"
DEWEIGHT_SCHEMA_VERSION: Literal["research.signal.deweighted.v1"] = "research.signal.deweighted.v1"
SUSPEND_SCHEMA_VERSION: Literal["research.signal.suspended.v1"] = "research.signal.suspended.v1"
RETIRE_SCHEMA_VERSION: Literal["research.signal.retired.v1"] = "research.signal.retired.v1"
CAPACITY_SCHEMA_VERSION: Literal["research.capacity.scaled.v1"] = "research.capacity.scaled.v1"
GUARDIAN_SCHEMA_VERSION: Literal["research.guardian.finding.v1"] = "research.guardian.finding.v1"
REPLENISH_SCHEMA_VERSION: Literal["research.replenishment.requested.v1"] = "research.replenishment.requested.v1"

MutationKind = Literal[
    "parameter_tune",
    "open_window",
    "noise",
    "threshold_change",
    "risk_core_change",
    "strategy_switch",
    "skip_gate",
    "direct_promotion",
]

EVENT_BUS_TOPIC_PRODUCERS: dict[str, frozenset[str]] = {
    RESEARCH_HYPOTHESIS_TOPIC: frozenset({HYPOTHESIS_AGENT_ID}),
    RESEARCH_VALIDATION_TOPIC: frozenset({VALIDATION_AGENT_ID}),
    RESEARCH_PROMOTION_TOPIC: frozenset({PROMOTION_AGENT_ID}),
    RESEARCH_MUTATION_TOPIC: frozenset({REFLECTOR_AGENT_ID}),
    RESEARCH_GOVERNANCE_TOPIC: frozenset({GOVERNANCE_AGENT_ID}),
    RESEARCH_DECAY_TOPIC: frozenset({MONITOR_AGENT_ID}),
    RESEARCH_DEWEIGHT_TOPIC: frozenset({MONITOR_AGENT_ID}),
    RESEARCH_SUSPEND_TOPIC: frozenset({MONITOR_AGENT_ID}),
    RESEARCH_RETIRE_TOPIC: frozenset({MONITOR_AGENT_ID}),
    RESEARCH_CAPACITY_TOPIC: frozenset({CAPACITY_AGENT_ID}),
    RESEARCH_GUARDIAN_TOPIC: frozenset({GUARDIAN_AGENT_ID}),
    RESEARCH_REPLENISH_TOPIC: frozenset({REPLENISH_AGENT_ID}),
}

# HMAC issuer guards. Existing (non-research) topics cannot register a guard.
EVENT_BUS_GUARDED_TOPICS: frozenset[str] = frozenset(
    {
        RESEARCH_PROMOTION_TOPIC,
        RESEARCH_VALIDATION_TOPIC,
        RESEARCH_MUTATION_TOPIC,
        RESEARCH_GOVERNANCE_TOPIC,
        RESEARCH_DECAY_TOPIC,
        RESEARCH_DEWEIGHT_TOPIC,
        RESEARCH_SUSPEND_TOPIC,
        RESEARCH_RETIRE_TOPIC,
        RESEARCH_CAPACITY_TOPIC,
        RESEARCH_GUARDIAN_TOPIC,
        RESEARCH_REPLENISH_TOPIC,
    }
)

_RATIONALE_MIN = 8


def _require_text(value: str, *, min_chars: int) -> str:
    text = value.strip()
    if len(text) < min_chars:
        raise ValueError(f"must contain at least {min_chars} non-whitespace characters")
    return text


class EconomicRationale(BaseModel):
    """Required economic / microstructure rationale. Missing or blank → refuse."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mechanism: str
    why_edge_exists: str
    other_side: str
    expected_regime: str
    falsification_criterion: str

    @field_validator(
        "mechanism",
        "why_edge_exists",
        "other_side",
        "expected_regime",
        "falsification_criterion",
    )
    @classmethod
    def _strip_required(cls, value: str) -> str:
        return _require_text(value, min_chars=_RATIONALE_MIN)


class HypothesisProposed(BaseModel):
    """Hypothesis on the research bus. A missing rationale is a schema violation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.hypothesis.proposed.v1"] = HYPOTHESIS_SCHEMA_VERSION
    hypothesis_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    generator_id: str = Field(min_length=1)
    kind: Literal["noise", "planted_edge"]
    instrument: Literal["ES", "NQ", "MES", "MNQ"]
    seed: int
    n_obs: int = Field(ge=241)
    mu: float
    sigma: float = Field(gt=0.0)
    planted: bool
    proposed_quantity: float = Field(gt=0.0)
    proposed_price: float = Field(gt=0.0)
    proposed_notional: float = Field(gt=0.0)
    is_size: int = Field(default=60, ge=2)
    oos_size: int = Field(default=30, ge=2)
    parent_config_id: str = ""
    overfit_in_sample: bool = False
    rationale: EconomicRationale


class OOSDistributionPayload(BaseModel):
    """OOS distribution. Always present on ValidationResult (values may be empty on reject)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    values: tuple[float | None, ...]
    median: float | None
    mean: float | None
    stdev: float | None
    worst: float | None
    best: float | None
    pct_positive: float | None


class DSRPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    probability: float | None
    observed_sr: float | None
    expected_max_sr: float | None
    sr_standard_error: float | None
    n_trials: int = Field(ge=0)
    n_observations: int = Field(ge=0)
    skew: float | None
    kurtosis: float | None
    formulation: str = Field(min_length=1)


class PBOPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pbo: float | None
    n_slices: int = Field(ge=0)
    n_combinations: int = Field(ge=0)
    n_configs: int = Field(ge=0)
    n_below_median: int = Field(ge=0)
    formulation: str = Field(min_length=1)
    logit_mean: float | None


class WFEPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    wfe: float | None
    mean_is_sharpe: float | None
    mean_oos_sharpe: float | None
    n_windows: int = Field(ge=0)
    mode: str
    parameter_stability: float | None


class RegimePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    vol_high_sharpe: float | None
    vol_low_sharpe: float | None
    trend_up_sharpe: float | None
    trend_down_sharpe: float | None
    robustness: float | None


class ValidationResult(BaseModel):
    """Gate outcome. Always carries OOS distribution, DSR, PBO, WFE and reject reasons.

    ``purge_applied`` / ``embargo_applied`` / ``cost_applied`` / ``regimes_complete``
    default to False so an incomplete payload cannot look like a PASS.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.validation.result.v1"] = VALIDATION_SCHEMA_VERSION
    hypothesis_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    passed: bool
    reject_reasons: tuple[str, ...]
    oos_distribution: OOSDistributionPayload
    dsr: DSRPayload
    pbo: PBOPayload
    wfe: WFEPayload
    regimes: RegimePayload
    n_oos_windows: int = Field(ge=0)
    median_oos_after_costs: float | None
    purge_applied: bool = False
    embargo_applied: bool = False
    cost_applied: bool = False
    cost_contract_root: str = ""
    cost_model_id: str = ""
    regimes_complete: bool = False
    report_sha256: str = Field(min_length=64, max_length=64)
    provenance_mac: str = Field(min_length=64, max_length=64)


class PromotionCandidate(BaseModel):
    """Proposal only. Never writes the live PromotionGate or live Risk Core."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.promotion.candidate.v1"] = PROMOTION_SCHEMA_VERSION
    hypothesis_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    instrument: Literal["ES", "NQ", "MES", "MNQ"]
    decision_kind: Literal["approved", "scaled"]
    scaled: bool
    quantity: float = Field(gt=0.0)
    notional: float = Field(gt=0.0)
    risk_reason: str = Field(min_length=1)
    validation_report_sha256: str = Field(min_length=64, max_length=64)
    validation_mac: str = Field(min_length=64, max_length=64)
    issue_mac: str = Field(min_length=64, max_length=64)


class ParameterGenome(BaseModel):
    """Tunable research parameters. Not Risk Core limits and not gate floors."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    instrument: Literal["ES", "NQ", "MES", "MNQ"]
    n_obs: int = Field(ge=241)
    mu: float
    sigma: float = Field(gt=0.0)
    quantity: float = Field(gt=0.0)
    price: float = Field(gt=0.0)
    is_size: int = Field(default=60, ge=2)
    oos_size: int = Field(default=30, ge=2)
    planted: bool
    kind: Literal["noise", "planted_edge"]
    overfit_in_sample: bool = False


class SignedReview(BaseModel):
    """HMAC-signed human review. Agent ids cannot be the reviewer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_id: str = Field(min_length=2)
    adr_sha256: str = Field(min_length=64, max_length=64)
    mutation_sha256: str = Field(min_length=64, max_length=64)
    verdict: Literal["approve", "reject"]
    signature: str = Field(min_length=64, max_length=64)


class MutationProposed(BaseModel):
    """Reflector/birth proposal only. Governance admits or rejects; this event never promotes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.mutation.proposed.v1"] = MUTATION_SCHEMA_VERSION
    mutation_id: str = Field(min_length=1)
    parent_config_id: str
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    kind: MutationKind
    target: str = Field(min_length=1)
    seed: int
    genome: ParameterGenome
    rationale: EconomicRationale
    adr_path: str = ""
    review: SignedReview | None = None
    provenance_mac: str = Field(min_length=64, max_length=64)


class GovernanceDecision(BaseModel):
    """Deterministic admit/reject. Protected surfaces are never applied by evolution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.governance.decision.v1"] = GOVERNANCE_SCHEMA_VERSION
    mutation_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    agent_id: str = Field(min_length=1)
    kind: MutationKind
    admitted: bool
    recorded_for_human: bool
    applied: bool
    reasons: tuple[str, ...]
    provenance_mac: str = Field(min_length=64, max_length=64)


SignalStage = Literal["active", "deweighted", "suspended", "retired"]
DecayMethod = Literal["ztest", "percentile", "cusum", "sprt", "combined"]
GuardianCadence = Literal["daily", "weekly"]
GuardianSeverity = Literal["ok", "warn", "violation"]
ReplenishReason = Literal["active_count", "capacity"]


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
