"""Typed payload contracts for EventBus and AgentBlackboard.

Contract policy is intentionally split in two tiers:
- critical event topics use strict schemas with ``extra="forbid"``
- experimental and non-critical topics stay on ``extra="allow"`` temporarily

See ``docs/architecture.md`` for the migration roadmap that balances strict
contract integrity with experimental agent space.
"""

from __future__ import annotations

from typing import Any, Literal, TypeVar

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


class RiskConfigMutationProposal(BaseModel):
    """Strict typed contract for risk config mutations (max_risk_percent, drawdown_kill_percent)
    originating from evolution hyperparam_suggestion paths (e.g. ProposalGenerator + meta wrappers).

    First small slice of Phase 3 D2 god decomp/firewall on meta_agent_core (SPF-003 per
    2026-05-31 analysis + MC D2 Red/highest-leverage post D4 scale). extra=forbid + required
    decision_context_id + source/dna/shadow ref enforce typed aperture, auditability, and
    tie to prior shadow (addresses D5 residual _apply_candidate gap at meta:1044-1047).

    Used by central apply fn in evolution_risk_proposal.py; optional bus publish under
    "evolution.risk_config.mutation" (with payload_model for contract).
    """

    model_config = ConfigDict(extra="forbid")

    decision_context_id: str = Field(min_length=1)  # e.g. from nightly/AB or upstream ctx
    source: str = Field(min_length=1)  # e.g. "meta_agent_core._apply_candidate" or "proposal_generator"
    dna_hash: str | None = None
    shadow_result_ref: str | None = None  # experiment_id from prior validate_risk_proposal_in_shadow (D5)
    proposed_values: dict[str, float] = Field(default_factory=dict)  # only the risk keys (max_risk_percent, drawdown_kill_percent)


TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC = "trading_engine.execution.aggregate"


class TradingEngineExecutionAggregate(BaseModel):
    """Strict EventBus contract for pre-trade execution consensus snapshots.

    Published only via EventBus (canonical). Unknown top-level keys are rejected;
    callers should pass payloads already filtered to known fields or use
    ``filter_payload_for_execution_aggregate``.
    """

    model_config = ConfigDict(extra="forbid")

    signal: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confluence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: float | None = None
    target: float | None = None
    reason: str | None = None
    why_no_trade: str | None = None
    chosen_strategy: str | None = None
    narrative_reasoning: str | None = None
    fib_levels_drawn: dict[str, Any] | None = None
    executed: bool | None = None
    pnl: float | None = None
    approved: bool | None = None
    hold_until_ts: float | None = None
    regime: str | None = None
    expected_value: float | None = None
    position_size_multiplier: float | None = Field(default=None, ge=0.0)


# Phase 2 Slice 18: First-class typed fill event with full lineage
EXECUTION_FILL_RECEIVED_TOPIC = "execution.fill.received"


class ExecutionFill(BaseModel):
    """Typed Event Bus contract for actual fills received from the broker.

    This is the downstream counterpart to the pre-trade lineage.
    Carries decision_context_id + prev_hash so the cryptographic chain
    continues from Final Arbitration / submission into real execution.

    Published best-effort via publish_validated when a fill is created
    or ingested (paper and live paths).
    """

    model_config = ConfigDict(extra="forbid")

    # Lineage (the important part for Phase 2)
    decision_context_id: str | None = None
    prev_hash: str | None = None
    prev_event_topic: str | None = None

    # Core fill data
    fill_id: str
    order_id: str | None = None
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: str
    commission: float = 0.0

    # Optional raw passthrough for broker-specific details
    raw: dict[str, Any] = Field(default_factory=dict)
    min_confluence: float | None = None
    meta_score: float | None = None
    agent_id: str | None = None
    sentiment_signal: str | None = None


def filter_payload_for_execution_aggregate(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop unknown keys so LLM/dream JSON can be validated against strict aggregate schema."""
    allowed = TradingEngineExecutionAggregate.model_fields.keys()
    return {k: v for k, v in payload.items() if k in allowed}


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
    decision_context_id: str | None = None  # Phase 2 Slice 08: upstream lineage root


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


#
# Birth Curriculum bounded context (thin orchestrator + dedicated handlers).
# Per ADR-0001: central bus, explicit contracts, fail-closed on violation.
# CurriculumOrchestrator must only emit/receive via EventBus.
#


class BirthCurriculumStarted(BaseModel):
    """Payload when a birth curriculum run begins."""

    model_config = ConfigDict(extra="forbid")

    curriculum_id: str = Field(min_length=1)
    stages: list[str]
    target_trades_cap: int = Field(ge=0)
    practice_mode: bool = False
    timestamp: str | None = None


class BirthCurriculumStageRequested(BaseModel):
    """Command-like fact: orchestrator requests a stage to begin execution."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    stage_index: int = Field(ge=0)
    target: int = Field(ge=0)
    stage_progress_pct: float = 0.0
    training_mode: str
    prefer_real: bool


class BirthCurriculumStageStarted(BaseModel):
    """Stage execution has begun (handler confirmed)."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    stage_index: int
    required_trades: int
    timestamp: str | None = None


class BirthCurriculumStageCompleted(BaseModel):
    """Stage finished. Pass/fail + receipt details. Strict for gate integrity."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    passed: bool
    trades: int = Field(ge=0)
    wins: int = Field(ge=0)
    hold_ratio: float
    provisional: bool = False
    message: str = ""
    receipt: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class BirthCurriculumStageAborted(BaseModel):
    """Terminal abort of curriculum or stage (fail-closed)."""

    model_config = ConfigDict(extra="forbid")

    stage: str | None = None
    reason: str  # e.g. "constitution_violation", "terminal_stall", "evolution_exhausted"
    detail: dict[str, Any] = Field(default_factory=dict)
    violations: int = 0


class BirthPlateauEntered(BaseModel):
    """Plateau escalation signal."""

    model_config = ConfigDict(extra="allow")

    stage: str
    winrate: float
    trades_at_detection: int
    evolution_step: int = 0


class BirthPhoenixCycle(BaseModel):
    """Phoenix loop cycle marker."""

    model_config = ConfigDict(extra="allow")

    cycle: int
    reason: str
    action: str | None = None
    preserve_cache: bool = True
    checkpoint_patch: dict[str, Any] | None = None


class BirthStageRolloutSnapshot(BaseModel):
    """Rollout tick signal consumed by birth SRP handlers."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = Field(min_length=1)
    signal: str = Field(min_length=1)
    stage: str
    context: dict[str, Any] = Field(default_factory=dict)


class BirthMetaPlan(BaseModel):
    """Meta-controller decision plan for a correlated rollout signal."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = Field(min_length=1)
    trigger: str = ""
    plan: dict[str, Any] = Field(default_factory=dict)


class BirthPlateauEvolutionStep(BaseModel):
    """Plateau evolution ladder step applied or requested."""

    model_config = ConfigDict(extra="allow")

    correlation_id: str = ""
    stage: str
    evolution_step: int = Field(ge=0)
    action: str
    detail: str = ""
    entered: bool = False


class BirthPlateauTrapDetected(BaseModel):
    """Over-trading trap fact for meta-controller consumption."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str
    detected: bool
    range_flat_ratio: float = 0.0
    range_round_trips: int = 0


class BirthStallRemediationCycle(BaseModel):
    """Stall remediation cycle started."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    cycle: int = Field(ge=1)
    max_cycles: int = Field(ge=1)
    winrate_at_start: float = 0.0


class BirthStallRemediationStep(BaseModel):
    """Stall remediation step advanced."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    cycle: int = Field(ge=1)
    step: int = Field(ge=1)
    max_steps: int = Field(ge=1)
    action: str | None = None
    detail: str = ""


class BirthAutonomyDecision(BaseModel):
    """Organism autonomy recovery dispatch."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    dispatch: str
    needs_attention: bool = False
    retryable: bool = True
    stall_reason: str = ""
    recommended_action: str = ""
    checkpoint_patch: dict[str, Any] | None = None
    autonomy_metrics: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class BirthCertificateRemediationRequested(BaseModel):
    """Certificate fast-path remediation gate signal."""

    model_config = ConfigDict(extra="forbid")

    progress_snapshot: dict[str, Any] = Field(default_factory=dict)
    checkpoint_state: dict[str, Any] = Field(default_factory=dict)
    fast_path_eligible: bool = False


class BirthWallTriggered(BaseModel):
    """Wall or stall trigger detected during certified birth research."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str
    trigger_type: str
    failure_key: str
    elapsed_stage_sec: float = 0.0
    constitution_violations: int = 0
    context: dict[str, Any] = Field(default_factory=dict)


class BirthAdaptationApplied(BaseModel):
    """Autonomous adaptation recovery applied after a wall trigger."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str
    reason: str
    adaptation_tier: int = 0
    retries_this_stage: int = 0
    chunk_target: int = 0
    escalation_level: int = 0
    parameter_patch: dict[str, Any] = Field(default_factory=dict)
    dispatch: str = "continue_loop"
    autonomous: bool = True
    recovery_kind: str = ""


class BirthAutonomyRecoveryMetrics(BaseModel):
    """Rolling autonomous recovery success metrics for birth stage."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str = ""
    stage: str
    wall_triggers_total: int = 0
    recovery_attempts: int = 0
    recovery_successes: int = 0
    autonomous_recovery_rate_pct: float = 0.0


class GateEntryPayload(BaseModel):
    """Minimal root event marking that an order intent has entered the authoritative admission chain."""

    model_config = ConfigDict(extra="forbid")

    decision_context_id: str
    symbol: str
    proposed_risk: float
    mode: str
    order_side: str | None = None


class RuntimeConfigReloaded(BaseModel):
    """Published after a successful runtime config hot-reload."""

    model_config = ConfigDict(extra="forbid")

    config_path: str
    changed_sections: list[str] = Field(default_factory=list)
    timestamp: str = ""


class RuntimeConfigReloadFailed(BaseModel):
    """Published when runtime config hot-reload is rejected (validation or immutable fields)."""

    model_config = ConfigDict(extra="forbid")

    config_path: str
    reason: str
    validation_errors: list[str] = Field(default_factory=list)
    immutable_fields: list[str] = Field(default_factory=list)
    timestamp: str = ""


class RuntimeConfigReloadRequested(BaseModel):
    """In-process nudge to reload config from disk without waiting for file watcher debounce."""

    model_config = ConfigDict(extra="forbid")

    config_path: str = ""
    source: str = "manual"
    timestamp: str = ""


EVENT_BUS_TOPIC_MODELS: dict[str, type[BaseModel]] = {
    "trading_engine.trade_signal.emitted": TradeIntent,
    "trading_engine.execution.aggregate": TradingEngineExecutionAggregate,
    "execution.fill.received": ExecutionFill,
    "trading_engine.dream_state.updated": DreamStateEventPayload,
    "risk.policy.decision": RiskVerdict,
    "risk.final_arbitration.result": FinalArbitrationResult,
    "admission.gate_entry": GateEntryPayload,
    "agent.rl.proposal": AgentProposalPayload,
    "agent.news.proposal": AgentProposalPayload,
    "agent.emotional_twin.proposal": AgentProposalPayload,
    "agent.swarm.proposal": AgentProposalPayload,
    "agent.tape.proposal": AgentProposalPayload,
    "evolution.proposal.created": EvolutionProposal,
    "evolution.shadow.verdict": ShadowResult,
    "evolution.promotion.decision": EvolutionPromotionDecision,
    "evolution.risk_config.mutation": RiskConfigMutationProposal,
    "safety.constitution.violation": ConstitutionViolation,
    "safety.constitution.audit": ConstitutionAudit,
    "meta.agent.reflection": AgentReflection,
    "meta.agent.thought": MetaAgentThought,
    "meta.community.knowledge": CommunityKnowledgeSnippet,
    "inference.llm.decision_context": LLMDecisionContext,
    "inference.adaptive_intelligence.state": AdaptiveIntelligenceState,
    "birth.curriculum.started": BirthCurriculumStarted,
    "birth.curriculum.stage.requested": BirthCurriculumStageRequested,
    "birth.curriculum.stage.started": BirthCurriculumStageStarted,
    "birth.curriculum.stage.completed": BirthCurriculumStageCompleted,
    "birth.curriculum.aborted": BirthCurriculumStageAborted,
    "birth.plateau.entered": BirthPlateauEntered,
    "birth.phoenix.cycle": BirthPhoenixCycle,
    "birth.stage.rollout.snapshot": BirthStageRolloutSnapshot,
    "birth.meta.plan": BirthMetaPlan,
    "birth.plateau.evolution.step": BirthPlateauEvolutionStep,
    "birth.plateau.trap.detected": BirthPlateauTrapDetected,
    "birth.stall.remediation.cycle": BirthStallRemediationCycle,
    "birth.stall.remediation.step": BirthStallRemediationStep,
    "birth.autonomy.decision": BirthAutonomyDecision,
    "birth.certificate.remediation.requested": BirthCertificateRemediationRequested,
    "birth.wall.triggered": BirthWallTriggered,
    "birth.adaptation.applied": BirthAdaptationApplied,
    "birth.autonomy.recovery.metrics": BirthAutonomyRecoveryMetrics,
    "runtime.config.reloaded": RuntimeConfigReloaded,
    "runtime.config.reload_failed": RuntimeConfigReloadFailed,
    "runtime.config.reload_requested": RuntimeConfigReloadRequested,
}

# Topics that must use registry models only, hard validation on publish_validated,
# and no silent validation failure (see EventBus).
CRITICAL_EVENT_BUS_TOPICS: frozenset[str] = frozenset(
    {
        "trading_engine.trade_signal.emitted",
        "trading_engine.execution.aggregate",
        "risk.policy.decision",
        "risk.final_arbitration.result",
        "admission.gate_entry",
        "agent.rl.proposal",
        "agent.news.proposal",
        "agent.emotional_twin.proposal",
        "agent.swarm.proposal",
        "agent.tape.proposal",
        "evolution.shadow.verdict",
        "evolution.promotion.decision",
        "safety.constitution.audit",
        # Birth curriculum critical boundaries (ADR-0001 + constitution fail-closed):
        # Any schema violation on stage completion or abort must hard-fail the birth run.
        "birth.curriculum.stage.completed",
        "birth.curriculum.aborted",
        # Phase 2 Slice 20: Downstream execution lineage now under the same strict critical contract
        # as the pre-trade gates and Final Arbitration. Schema violations on fill events will
        # now raise (fail-closed) instead of being swallowed.
        EXECUTION_FILL_RECEIVED_TOPIC,
    }
)

BLACKBOARD_TOPIC_MODELS: dict[str, type[BaseModel]] = {
    "agent.rl.proposal": AgentProposalPayload,
    "agent.news.proposal": AgentProposalPayload,
    "agent.emotional_twin.proposal": AgentProposalPayload,
    "agent.swarm.proposal": AgentProposalPayload,
    "agent.tape.proposal": AgentProposalPayload,
    "agent.swarm.snapshot": AgentProposalPayload,
    "market.tape": MarketTapePayload,
    "meta.reflection": AgentReflection,
    "meta.hyperparameters": MetaHyperparametersPayload,
    "meta.retraining": MetaRetrainingPayload,
    "meta.bible_update": MetaBibleUpdatePayload,
    "meta.evolution_result": MetaEvolutionResultPayload,
    "meta.dna_lineage": MetaDnaLineagePayload,
    "agent.meta.proposal": AgentMetaProposalPayload,
}


def model_validate_payload_with_instance(
    *,
    payload: dict[str, Any],
    payload_model: type[BaseModel],
) -> tuple[dict[str, Any], BaseModel]:
    """Validate payload; return JSON-safe dict plus the Pydantic instance for subscribers."""
    instance = payload_model.model_validate(payload)
    return instance.model_dump(mode="json", exclude_none=False), instance


def validate_payload_with_model(
    *,
    payload: dict[str, Any],
    payload_model: type[BaseModel],
) -> dict[str, Any]:
    """Validate and convert payload to a JSON-safe dict."""
    dumped, _ = model_validate_payload_with_instance(payload=payload, payload_model=payload_model)
    return dumped


def validate_registered_event_payload(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate payload using event-topic registry when a model is configured."""
    topic_key = str(topic).strip().lower()
    model_cls = EVENT_BUS_TOPIC_MODELS.get(topic_key)
    if model_cls is None:
        if topic_key in CRITICAL_EVENT_BUS_TOPICS:
            msg = f"Critical event topic {topic_key!r} is missing from EVENT_BUS_TOPIC_MODELS"
            raise ValueError(msg)
        return dict(payload)
    return validate_payload_with_model(payload=payload, payload_model=model_cls)


def registered_event_topics() -> frozenset[str]:
    return frozenset(EVENT_BUS_TOPIC_MODELS.keys())


def is_schema_violation(exc: Exception) -> bool:
    return isinstance(exc, ValidationError)


TPayloadModel = TypeVar("TPayloadModel", bound=BaseModel)


def typed_payload_from_event(event: Any, model: type[TPayloadModel]) -> TPayloadModel:
    """Resolve a validated Pydantic instance from DomainEvent, BlackboardEvent, or legacy dict events."""
    inst = getattr(event, "payload_instance", None)
    if isinstance(inst, model):
        return inst
    if hasattr(event, "typed_payload"):
        return event.typed_payload(model)
    raw = getattr(event, "payload", None)
    if isinstance(raw, model):
        return raw
    if isinstance(raw, dict):
        return model.model_validate(raw)
    return model.model_validate({})
