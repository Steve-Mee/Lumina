"""Typed payload contracts for EventBus and AgentBlackboard.

Contract policy is intentionally split in two tiers:
- critical event topics use strict schemas with ``extra="forbid"``
- experimental and non-critical topics stay on ``extra="allow"`` temporarily

See ``docs/architecture.md`` for the migration roadmap that balances strict
contract integrity with experimental agent space.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from lumina_core.risk.schemas import ArbitrationResult


#
# Tier A: Critical execution and risk contracts (REAL integrity boundary).
# These contracts are strict by design: unknown fields are rejected.
#


class TradeIntent(BaseModel):
    """Contract for trade-oriented signal payloads."""

    model_config = ConfigDict(extra="forbid")

    signal: str | None = None
    confidence: float | None = None
    stop: float | None = None
    target: float | None = None
    reason: str | None = None
    why_no_trade: str | None = None
    confluence_score: float | None = None
    regime: str | None = None
    hold_until_ts: float | None = None
    position_size_multiplier: float | None = Field(default=None, ge=0.0)
    min_confluence_override: float | None = None


class RiskVerdict(BaseModel):
    """Contract for risk decision and gating payloads."""

    model_config = ConfigDict(extra="forbid")

    approved: bool | None = None
    reason: str | None = None
    limit: str | None = None
    value: float | None = None
    risk_adjustment: float | None = None
    max_risk_percent_multiplier: float | None = Field(default=None, ge=0.0)
    rl_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class FinalArbitrationResult(ArbitrationResult):
    """Event-bus alias for canonical risk arbitration result contract."""


class EvolutionPromotionDecision(BaseModel):
    """Contract for REAL-facing promotion gate decisions."""

    model_config = ConfigDict(extra="forbid")

    dna_hash: str = Field(min_length=1)
    allowed: bool
    reason: str = Field(min_length=1)
    stage: Literal["shadow", "promotion_gate", "human_approval", "final"]
    mode: Literal["SIM", "PAPER", "REAL"] | None = None
    evidence_ref: str | None = None


class ShadowResult(BaseModel):
    """Contract for shadow deployment verdict payloads."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["pass", "fail", "pending"]
    dna_hash: str | None = None
    sample_size: int | None = Field(default=None, ge=0)
    pnl: float | None = None


#
# Tier B: Experimental and agent-cognition contracts (emergent space).
# These remain intentionally flexible with extra="allow" while fields stabilize.
# Migration path: inventory frequently used dynamic fields and promote them into
# explicit contracts before moving a topic to strict mode.
#


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


class DreamStateEventPayload(TradeIntent):
    """Experimental dream-state payload envelope.

    This topic intentionally remains extensible while dream-state fields are
    being stabilized and gradually migrated into explicit schema fields.
    """

    model_config = ConfigDict(extra="allow")


DreamState = DreamStateEventPayload


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


class ExecutionAggregatePayload(BaseModel):
    """Contract for execution aggregate topic payloads."""

    model_config = ConfigDict(extra="allow")

    signal: str | None = None
    executed: bool | None = None
    pnl: float | None = None
    approved: bool | None = None
    reason: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MarketTapePayload(BaseModel):
    """Contract for market tape snapshots."""

    model_config = ConfigDict(extra="allow")

    symbol: str | None = None
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = Field(default=None, ge=0.0)
    signal: str | None = None


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


EVENT_BUS_TOPIC_MODELS: dict[str, type[BaseModel]] = {
    "trading_engine.trade_signal.emitted": TradeIntent,
    "trading_engine.dream_state.updated": DreamStateEventPayload,
    "risk.policy.decision": RiskVerdict,
    "risk.final_arbitration.result": FinalArbitrationResult,
    "evolution.proposal.created": EvolutionProposal,
    "evolution.shadow.verdict": ShadowResult,
    "evolution.promotion.decision": EvolutionPromotionDecision,
    "safety.constitution.violation": ConstitutionViolation,
    "safety.constitution.audit": ConstitutionAudit,
    "meta.agent.reflection": AgentReflection,
    "meta.agent.thought": MetaAgentThought,
    "meta.community.knowledge": CommunityKnowledgeSnippet,
    "inference.llm.decision_context": LLMDecisionContext,
}

BLACKBOARD_TOPIC_MODELS: dict[str, type[BaseModel]] = {
    "agent.rl.proposal": AgentProposalPayload,
    "agent.news.proposal": AgentProposalPayload,
    "agent.emotional_twin.proposal": AgentProposalPayload,
    "agent.swarm.proposal": AgentProposalPayload,
    "agent.tape.proposal": AgentProposalPayload,
    "agent.swarm.snapshot": AgentProposalPayload,
    "market.tape": MarketTapePayload,
    "execution.aggregate": ExecutionAggregatePayload,
    "meta.reflection": AgentReflection,
    "meta.hyperparameters": MetaHyperparametersPayload,
    "meta.retraining": MetaRetrainingPayload,
    "meta.bible_update": MetaBibleUpdatePayload,
    "meta.evolution_result": MetaEvolutionResultPayload,
    "meta.dna_lineage": MetaDnaLineagePayload,
    "agent.meta.proposal": AgentMetaProposalPayload,
}


def validate_payload_with_model(
    *,
    payload: dict[str, Any],
    payload_model: type[BaseModel],
) -> dict[str, Any]:
    """Validate and convert payload to a JSON-safe dict."""
    validated = payload_model.model_validate(payload)
    return validated.model_dump(mode="json", exclude_none=False)


def validate_registered_event_payload(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate payload using event-topic registry when a model is configured."""
    model_cls = EVENT_BUS_TOPIC_MODELS.get(str(topic).strip().lower())
    if model_cls is None:
        return dict(payload)
    return validate_payload_with_model(payload=payload, payload_model=model_cls)


def registered_event_topics() -> frozenset[str]:
    return frozenset(EVENT_BUS_TOPIC_MODELS.keys())


def is_schema_violation(exc: Exception) -> bool:
    return isinstance(exc, ValidationError)
