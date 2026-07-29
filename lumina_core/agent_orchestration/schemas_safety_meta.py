"""Typed EventBus / Blackboard payload contracts (safety_meta).

Canonical re-export surface: ``lumina_core.agent_orchestration.schemas``.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

class ConstitutionViolation(BaseModel):
    """Contract for constitution violation events."""

    model_config = ConfigDict(extra="allow")

    principle_name: str
    severity: str
    description: str | None = None
    detail: str | None = None
    mode: str | None = None


class ConstitutionAudit(BaseModel):
    """Contract for constitution audit summaries."""

    model_config = ConfigDict(extra="forbid")

    phase: str
    passed: bool
    mode: str
    dna_hash: str | None = None
    violation_codes: list[str] = Field(default_factory=list)
    summary: str | None = None


# -------------------------------------------------------------------
# Architecture Meta (next evolution layer) — typed contracts
# -------------------------------------------------------------------

class ArchHealthSnapshotPayload(BaseModel):
    """Observable snapshot for architecture health (used by meta controller)."""

    model_config = ConfigDict(extra="forbid")

    god_file_count: int = 0
    boundary_violations: int = 0
    pydantic_model_count: int = 0
    ruff_violations_core: int = 0
    avg_module_loc: float = 0.0
    todo_density: float = 0.0
    total_core_loc: int = 0
    arch_health_score: float = 5.0
    timestamp: str | None = None


class ArchMutationProposalPayload(BaseModel):
    """Contract for an architecture mutation proposal."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    mutation_type: str
    target_file: str
    description: str = ""
    diff: str = ""
    expected_delta: float = 0.0
    rationale: str = ""
    before_score: float = 5.0
    constitution_passed: bool = False
    sandbox_passed: bool = False
    decision_context_id: str = ""


class ArchPromotionDecisionPayload(BaseModel):
    """Human gate outcome for arch proposal."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    approved: bool
    approver: str = ""
    reason: str = ""
    timestamp: str = ""
class AdaptiveIntelligenceState(BaseModel):
    """Typed contract for adaptive intelligence runtime status."""

    model_config = ConfigDict(extra="forbid")

    tier: Literal["high", "standard", "light"]
    mode: Literal["auto", "force_high", "force_standard", "force_light"]
    reasoning_mode: str
    degraded_state: bool
    status_reason: str
    recommended_model: str
    recommended_provider: str
    context_length: int = Field(ge=0)
    last_probe_error: str | None = None
    source: str | None = None
    timestamp: str | None = None


class AgentReflection(BaseModel):
    """Contract for reflective meta-agent summary payloads."""

    model_config = ConfigDict(extra="allow")

    window_hours: int | None = Field(default=None, ge=0)
    events_observed: int | None = Field(default=None, ge=0)
    avg_aggregate_confidence: float | None = None
    win_rate: float | None = None
    net_pnl: float | None = None
    sharpe: float | None = None
    reflection_confidence: float | None = None
    timestamp: str | None = None
class MetaAgentThought(BaseModel):
    """Flexible thought payload emitted by meta-agent cognition loops."""

    model_config = ConfigDict(extra="allow")

    thought_id: str | None = None
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    summary: str | None = None
    context: dict[str, Any] | None = None
    timestamp: str | None = None


class CommunityKnowledgeSnippet(BaseModel):
    """Flexible community knowledge snippet payload."""

    model_config = ConfigDict(extra="allow")

    snippet_id: str | None = None
    source: str | None = None
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None
    timestamp: str | None = None


class LLMDecisionContext(BaseModel):
    """Flexible context envelope for LLM advisory decision traces."""

    model_config = ConfigDict(extra="allow")

    model_name: str | None = None
    prompt_id: str | None = None
    llm_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    recommendation: str | None = None
    rationale: str | None = None
    context: dict[str, Any] | None = None
    timestamp: str | None = None


class AgentProposalPayload(BaseModel):
    """Contract for blackboard proposal topics."""

    model_config = ConfigDict(extra="allow")

    signal: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    qty: float | None = Field(default=None, gt=0.0)
    reason: str | None = None
    decision_context_id: str | None = None  # Phase 2 Slice 08: upstream lineage root
class MetaHyperparametersPayload(BaseModel):
    """Contract for hyperparameter update payloads."""

    model_config = ConfigDict(extra="allow")

    ppo_learning_rate: float | None = Field(default=None, gt=0.0)
    ppo_clip_range: float | None = Field(default=None, ge=0.0)
    position_size_multiplier: float | None = Field(default=None, ge=0.0)


class MetaRetrainingPayload(BaseModel):
    """Contract for retraining decisions."""

    model_config = ConfigDict(extra="allow")

    triggered: bool | None = None
    executed: bool | None = None
    reason: str | None = None


class MetaBibleUpdatePayload(BaseModel):
    """Contract for bible update payloads."""

    model_config = ConfigDict(extra="allow")

    timestamp: str | None = None
    summary: str | None = None


class MetaEvolutionResultPayload(BaseModel):
    """Contract for evolution result payloads."""

    model_config = ConfigDict(extra="allow")

    status: str | None = None
    proposal: dict[str, Any] | None = None
    timestamp: str | None = None


class MetaDnaLineagePayload(BaseModel):
    """Contract for DNA lineage tracking."""

    model_config = ConfigDict(extra="allow")

    active_hash: str | None = None
    active_version: str | None = None
    candidate_hash: str | None = None
    candidate_version: str | None = None
    lineage_hash: str | None = None
    evolution_status: str | None = None
    timestamp: str | None = None


class AgentMetaProposalPayload(BaseModel):
    """Contract for self-evolution proposal payloads."""

    model_config = ConfigDict(extra="allow")

    status: str | None = None
    proposal: dict[str, Any] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    timestamp: str | None = None

