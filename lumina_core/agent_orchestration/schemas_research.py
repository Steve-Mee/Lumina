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

HYPOTHESIS_AGENT_ID = "hypothesis_agent"
VALIDATION_AGENT_ID = "validation_agent"
PROMOTION_AGENT_ID = "promotion_agent"
REFLECTOR_AGENT_ID = "reflector_agent"
BIRTH_AGENT_ID = "birth_agent"
GOVERNANCE_AGENT_ID = "governance_agent"

HYPOTHESIS_SCHEMA_VERSION: Literal["research.hypothesis.proposed.v1"] = "research.hypothesis.proposed.v1"
VALIDATION_SCHEMA_VERSION: Literal["research.validation.result.v1"] = "research.validation.result.v1"
PROMOTION_SCHEMA_VERSION: Literal["research.promotion.candidate.v1"] = "research.promotion.candidate.v1"
MUTATION_SCHEMA_VERSION: Literal["research.mutation.proposed.v1"] = "research.mutation.proposed.v1"
GOVERNANCE_SCHEMA_VERSION: Literal["research.governance.decision.v1"] = "research.governance.decision.v1"

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
}

# HMAC issuer guards. Existing (non-research) topics cannot register a guard.
EVENT_BUS_GUARDED_TOPICS: frozenset[str] = frozenset(
    {
        RESEARCH_PROMOTION_TOPIC,
        RESEARCH_VALIDATION_TOPIC,
        RESEARCH_MUTATION_TOPIC,
        RESEARCH_GOVERNANCE_TOPIC,
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
