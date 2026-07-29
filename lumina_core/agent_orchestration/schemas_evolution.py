"""Typed EventBus / Blackboard payload contracts (evolution).

Canonical re-export surface: ``lumina_core.agent_orchestration.schemas``.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

class EvolutionPromotionDecision(BaseModel):
    """Contract for REAL-facing promotion gate decisions."""

    model_config = ConfigDict(extra="forbid")

    dna_hash: str = Field(min_length=1)
    allowed: bool
    reason: str = Field(min_length=1)
    stage: Literal["shadow", "promotion_gate", "human_approval", "final"]
    mode: Literal["SIM", "PAPER", "REAL"] | None = None
    evidence_ref: str | None = None
class EvolutionProposal(BaseModel):
    """Contract for evolution proposal and status payloads."""

    model_config = ConfigDict(extra="allow")

    status: str | None = None
    proposal: dict[str, Any] | None = None
    dna: dict[str, Any] | None = None
    generations_run: int | None = Field(default=None, ge=0)
    promotions: int | None = Field(default=None, ge=0)
    best_fitness: float | None = None
    timestamp: str | None = None
class CodeMutationProposalPayload(BaseModel):
    """Typed contract for sandboxed trading-code evolution proposals (ADR-0033)."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    operator: str
    target: str
    description: str = ""
    estimated_loc: int = Field(default=0, ge=0)
    decision_context_id: str = ""
    constitution_passed: bool = False
    sandbox_passed: bool = False


class CodeSandboxResultPayload(BaseModel):
    """Sandbox evaluation outcome for a code-evolution proposal."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    passed: bool
    score: float = 0.0
    violations: list[str] = Field(default_factory=list)
    input_hash: str = ""
    output_hash: str = ""
    timed_out: bool = False
    error: str = ""
    mode: str = "sim"


class CodeEvolutionDecisionPayload(BaseModel):
    """Final pipeline decision for a code-evolution proposal (evaluate-only v1)."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    constitution_passed: bool = False
    twin_recommendation: bool = False
    twin_effective: bool = False
    sandbox_passed: bool = False
    applied: bool = False
    reason: str = ""
    violations: list[str] = Field(default_factory=list)
    timestamp: str = ""


class TwinDecisionEvent(BaseModel):
    """ApprovalTwin promotion evaluation (ADR-0031)."""

    model_config = ConfigDict(extra="allow")

    dna_hash: str
    recommendation: bool
    confidence: float = Field(ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)
    explanation: str = ""
    call: str = "evaluate_dna_promotion"


class TwinTrainingUpdateEvent(BaseModel):
    """ApprovalTwin RLHF-light training metrics (ADR-0031)."""

    model_config = ConfigDict(extra="allow")

    records_processed: int = Field(ge=0)
    updates: int = Field(ge=0)
    avg_prediction_error: float = 0.0
    reward: float = 0.0
    training_steps: int = Field(ge=0, default=0)


class TwinShadowObservationEvent(BaseModel):
    """Non-blocking Twin observe of shadow/promotion/constitution outcomes (ADR-0031 finish).

    Observability only — never critical. Twin records agreement/disagreement without
    mutating gate decisions.
    """

    model_config = ConfigDict(extra="allow")

    dna_hash: str = ""
    source_topic: str
    twin_recommendation: bool
    observed_allowed_or_pass: bool
    agreed: bool
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_flags: list[str] = Field(default_factory=list)
    explanation: str = ""


class TwinModePromotionEvent(BaseModel):
    """ApprovalTwin judgment-mode promotion evaluation (shadow → assisted → full_auto)."""

    model_config = ConfigDict(extra="allow")

    current_mode: str
    target_mode: str
    promoted: bool
    fail_reasons: list[str] = Field(default_factory=list)
    reason: str = ""
    agreement_pct: float = 0.0
    false_positive_pct: float = 100.0
    samples: int = Field(ge=0, default=0)

