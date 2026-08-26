"""Typed payload contracts for EventBus and AgentBlackboard.

Contract policy is intentionally split in two tiers:
- critical event topics use strict schemas with ``extra="forbid"``
- experimental and non-critical topics stay on ``extra="allow"`` temporarily

Domain modules (re-exported here for stable imports):
``schemas_trading``, ``schemas_risk``, ``schemas_evolution``,
``schemas_safety_meta``, ``schemas_birth``, ``schemas_runtime``.
"""
from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from lumina_core.agent_orchestration.schemas_birth import *  # noqa: F403
from lumina_core.agent_orchestration.schemas_evolution import *  # noqa: F403
from lumina_core.agent_orchestration.schemas_risk import *  # noqa: F403
from lumina_core.agent_orchestration.schemas_runtime import *  # noqa: F403
from lumina_core.agent_orchestration.schemas_safety_meta import *  # noqa: F403
from lumina_core.agent_orchestration.schemas_trading import *  # noqa: F403

# Explicit names for static analyzers / star-import clarity
from lumina_core.agent_orchestration.schemas_birth import (
    BirthAdaptationApplied,
    BirthAutonomyDecision,
    BirthAutonomyRecoveryMetrics,
    BirthCertificateRemediationRequested,
    BirthCurriculumStageAborted,
    BirthCurriculumStageCompleted,
    BirthCurriculumStageRequested,
    BirthCurriculumStageStarted,
    BirthCurriculumStarted,
    BirthMetaPlan,
    BirthPhase2GateResult,
    BirthPhase2InstanceProposal,
    BirthPhase2ParamProposal,
    BirthPhase2WallProposal,
    BirthPhoenixCycle,
    BirthPlateauEntered,
    BirthPlateauEvolutionStep,
    BirthPlateauTrapDetected,
    BirthStageRolloutSnapshot,
    BirthStallRemediationCycle,
    BirthStallRemediationStep,
    BirthWallTriggered,
)
from lumina_core.agent_orchestration.schemas_evolution import (
    CodeEvolutionDecisionPayload,
    CodeMutationProposalPayload,
    CodeSandboxResultPayload,
    EvolutionPromotionDecision,
    EvolutionProposal,
    OverlayLoadedPayload,
    TwinDecisionEvent,
    TwinEscalationEvent,
    TwinModePromotionEvent,
    TwinShadowObservationEvent,
    TwinTrainingUpdateEvent,
)
from lumina_core.agent_orchestration.schemas_risk import (
    AdmissionLineageCheckedPayload,
    FinalArbitrationResult,
    GateEntryPayload,
    RiskConfigMutationProposal,
    RiskVerdict,
    ShadowResult,
)
from lumina_core.agent_orchestration.schemas_runtime import (
    RuntimeConfigReloadFailed,
    RuntimeConfigReloadRequested,
    RuntimeConfigReloaded,
)
from lumina_core.agent_orchestration.schemas_safety_meta import (
    AdaptiveIntelligenceState,
    AgentMetaProposalPayload,
    AgentProposalPayload,
    AgentReflection,
    CommunityKnowledgeSnippet,
    ConstitutionAudit,
    ConstitutionViolation,
    LLMDecisionContext,
    MetaAgentThought,
    MetaBibleUpdatePayload,
    MetaDnaLineagePayload,
    MetaEvolutionResultPayload,
    MetaHyperparametersPayload,
    MetaRetrainingPayload,
)
from lumina_core.agent_orchestration.schemas_trading import (
    EXECUTION_FILL_RECEIVED_TOPIC,
    DreamStateEventPayload,
    ExecutionFill,
    MarketTapePayload,
    TradeIntent,
    TradingEngineExecutionAggregate,
)

EVENT_BUS_TOPIC_MODELS: dict[str, type[BaseModel]] = {
    "trading_engine.trade_signal.emitted": TradeIntent,
    "trading_engine.execution.aggregate": TradingEngineExecutionAggregate,
    "execution.fill.received": ExecutionFill,
    "trading_engine.dream_state.updated": DreamStateEventPayload,
    "risk.policy.decision": RiskVerdict,
    "risk.final_arbitration.result": FinalArbitrationResult,
    "risk.admission.lineage_checked": AdmissionLineageCheckedPayload,
    "admission.gate_entry": GateEntryPayload,
    "agent.rl.proposal": AgentProposalPayload,
    "agent.news.proposal": AgentProposalPayload,
    "agent.emotional_twin.proposal": AgentProposalPayload,
    "agent.swarm.proposal": AgentProposalPayload,
    "agent.tape.proposal": AgentProposalPayload,
    "evolution.proposal.created": EvolutionProposal,
    "evolution.shadow.verdict": ShadowResult,
    "evolution.promotion.decision": EvolutionPromotionDecision,
    "evolution.twin.decision": TwinDecisionEvent,
    "evolution.twin.training_update": TwinTrainingUpdateEvent,
    "evolution.twin.shadow_observation": TwinShadowObservationEvent,
    "evolution.twin.mode_promotion": TwinModePromotionEvent,
    "evolution.twin.escalation": TwinEscalationEvent,
    "evolution.risk_config.mutation": RiskConfigMutationProposal,
    "evolution.code.proposal.created": CodeMutationProposalPayload,
    "evolution.code.sandbox.result": CodeSandboxResultPayload,
    "evolution.code.decision": CodeEvolutionDecisionPayload,
    "evolution.code.overlay.loaded": OverlayLoadedPayload,
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
    "birth.phase2.wall.proposal": BirthPhase2WallProposal,
    "birth.phase2.param.proposal": BirthPhase2ParamProposal,
    "birth.phase2.instance.proposal": BirthPhase2InstanceProposal,
    "birth.phase2.gate.result": BirthPhase2GateResult,
    "runtime.config.reloaded": RuntimeConfigReloaded,
    "runtime.config.reload_failed": RuntimeConfigReloadFailed,
    "runtime.config.reload_requested": RuntimeConfigReloadRequested,
}

CRITICAL_EVENT_BUS_TOPICS: frozenset[str] = frozenset(
    {
        "trading_engine.trade_signal.emitted",
        "trading_engine.execution.aggregate",
        "risk.policy.decision",
        "risk.final_arbitration.result",
        "risk.admission.lineage_checked",
        "admission.gate_entry",
        "agent.rl.proposal",
        "agent.news.proposal",
        "agent.emotional_twin.proposal",
        "agent.swarm.proposal",
        "agent.tape.proposal",
        "evolution.shadow.verdict",
        "evolution.promotion.decision",
        "safety.constitution.audit",
        "birth.curriculum.stage.completed",
        "birth.curriculum.aborted",
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
