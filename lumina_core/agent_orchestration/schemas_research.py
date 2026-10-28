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

HYPOTHESIS_AGENT_ID = "hypothesis_agent"
VALIDATION_AGENT_ID = "validation_agent"
PROMOTION_AGENT_ID = "promotion_agent"

HYPOTHESIS_SCHEMA_VERSION: Literal["research.hypothesis.proposed.v1"] = "research.hypothesis.proposed.v1"
VALIDATION_SCHEMA_VERSION: Literal["research.validation.result.v1"] = "research.validation.result.v1"
PROMOTION_SCHEMA_VERSION: Literal["research.promotion.candidate.v1"] = "research.promotion.candidate.v1"

EVENT_BUS_TOPIC_PRODUCERS: dict[str, frozenset[str]] = {
    RESEARCH_HYPOTHESIS_TOPIC: frozenset({HYPOTHESIS_AGENT_ID}),
    RESEARCH_VALIDATION_TOPIC: frozenset({VALIDATION_AGENT_ID}),
    RESEARCH_PROMOTION_TOPIC: frozenset({PROMOTION_AGENT_ID}),
}

# PromotionCandidate may only be issued by PromotionAgent (HMAC guard on the bus).
EVENT_BUS_GUARDED_TOPICS: frozenset[str] = frozenset({RESEARCH_PROMOTION_TOPIC})

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
    """Gate outcome. Always carries OOS distribution, DSR, PBO, WFE and reject reasons."""

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
