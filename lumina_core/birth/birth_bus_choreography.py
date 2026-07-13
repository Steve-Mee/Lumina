"""EventBus choreography helpers for birth bounded context."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus

TPayload = TypeVar("TPayload", bound=BaseModel)

TOPIC_SNAPSHOT = "birth.stage.rollout.snapshot"
TOPIC_META_PLAN = "birth.meta.plan"
TOPIC_PLATEAU_ENTERED = "birth.plateau.entered"
TOPIC_PLATEAU_EVOLUTION = "birth.plateau.evolution.step"
TOPIC_PLATEAU_TRAP = "birth.plateau.trap.detected"
TOPIC_REMEDIATION_CYCLE = "birth.stall.remediation.cycle"
TOPIC_REMEDIATION_STEP = "birth.stall.remediation.step"
TOPIC_PHOENIX_CYCLE = "birth.phoenix.cycle"
TOPIC_AUTONOMY_DECISION = "birth.autonomy.decision"
TOPIC_CERT_REMEDIATION = "birth.certificate.remediation.requested"
TOPIC_WALL_TRIGGERED = "birth.wall.triggered"
TOPIC_ADAPTATION_APPLIED = "birth.adaptation.applied"
TOPIC_AUTONOMY_RECOVERY_METRICS = "birth.autonomy.recovery.metrics"


def latest_for_correlation(
    bus: EventBus,
    topic: str,
    correlation_id: str,
    *,
    limit: int = 32,
) -> DomainEvent | None:
    """Return the most recent event on ``topic`` matching ``correlation_id``."""
    cid = str(correlation_id)
    for event in reversed(bus.history(topic, limit=limit)):
        meta_cid = str(event.metadata.get("correlation_id", "") or "")
        payload_cid = ""
        if isinstance(event.payload, dict):
            payload_cid = str(event.payload.get("correlation_id", "") or "")
        if meta_cid == cid or payload_cid == cid:
            return event
    return None


def typed_for_correlation(
    bus: EventBus,
    topic: str,
    correlation_id: str,
    model: type[TPayload],
    *,
    limit: int = 32,
) -> TPayload | None:
    event = latest_for_correlation(bus, topic, correlation_id, limit=limit)
    if event is None:
        return None
    return event.typed_payload(model)


def publish_snapshot(
    bus: EventBus,
    *,
    producer: str,
    correlation_id: str,
    signal: str,
    stage: str,
    context: dict[str, Any],
) -> DomainEvent:
    from lumina_core.agent_orchestration.schemas import BirthStageRolloutSnapshot

    payload = BirthStageRolloutSnapshot(
        correlation_id=correlation_id,
        signal=signal,
        stage=stage,
        context=context,
    )
    return bus.publish(
        topic=TOPIC_SNAPSHOT,
        producer=producer,
        payload=payload.model_dump(mode="json"),
        metadata={"correlation_id": correlation_id},
    )


def publish_wall_triggered(
    bus: EventBus,
    *,
    producer: str,
    correlation_id: str,
    stage: str,
    trigger_type: str,
    failure_key: str,
    elapsed_stage_sec: float,
    constitution_violations: int,
    context: dict[str, Any],
) -> DomainEvent:
    from lumina_core.agent_orchestration.schemas import BirthWallTriggered

    payload = BirthWallTriggered(
        correlation_id=correlation_id,
        stage=stage,
        trigger_type=trigger_type,
        failure_key=failure_key,
        elapsed_stage_sec=float(elapsed_stage_sec),
        constitution_violations=int(constitution_violations),
        context=context,
    )
    return bus.publish(
        topic=TOPIC_WALL_TRIGGERED,
        producer=producer,
        payload=payload.model_dump(mode="json"),
        metadata={"correlation_id": correlation_id},
    )


def publish_adaptation_applied(
    bus: EventBus,
    *,
    producer: str,
    correlation_id: str,
    stage: str,
    reason: str,
    adaptation_tier: int,
    retries_this_stage: int,
    chunk_target: int,
    escalation_level: int,
    parameter_patch: dict[str, Any],
    dispatch: str,
    recovery_kind: str,
) -> DomainEvent:
    from lumina_core.agent_orchestration.schemas import BirthAdaptationApplied

    payload = BirthAdaptationApplied(
        correlation_id=correlation_id,
        stage=stage,
        reason=reason,
        adaptation_tier=int(adaptation_tier),
        retries_this_stage=int(retries_this_stage),
        chunk_target=int(chunk_target),
        escalation_level=int(escalation_level),
        parameter_patch=parameter_patch,
        dispatch=dispatch,
        autonomous=True,
        recovery_kind=recovery_kind,
    )
    return bus.publish(
        topic=TOPIC_ADAPTATION_APPLIED,
        producer=producer,
        payload=payload.model_dump(mode="json"),
        metadata={"correlation_id": correlation_id},
    )


def publish_recovery_metrics(
    bus: EventBus,
    *,
    producer: str,
    correlation_id: str,
    stage: str,
    wall_triggers_total: int,
    recovery_attempts: int,
    recovery_successes: int,
    autonomous_recovery_rate_pct: float,
) -> DomainEvent:
    from lumina_core.agent_orchestration.schemas import BirthAutonomyRecoveryMetrics

    payload = BirthAutonomyRecoveryMetrics(
        correlation_id=correlation_id,
        stage=stage,
        wall_triggers_total=int(wall_triggers_total),
        recovery_attempts=int(recovery_attempts),
        recovery_successes=int(recovery_successes),
        autonomous_recovery_rate_pct=float(autonomous_recovery_rate_pct),
    )
    return bus.publish(
        topic=TOPIC_AUTONOMY_RECOVERY_METRICS,
        producer=producer,
        payload=payload.model_dump(mode="json"),
        metadata={"correlation_id": correlation_id},
    )


__all__ = [
    "TOPIC_ADAPTATION_APPLIED",
    "TOPIC_AUTONOMY_DECISION",
    "TOPIC_AUTONOMY_RECOVERY_METRICS",
    "TOPIC_CERT_REMEDIATION",
    "TOPIC_META_PLAN",
    "TOPIC_PHOENIX_CYCLE",
    "TOPIC_PLATEAU_ENTERED",
    "TOPIC_PLATEAU_EVOLUTION",
    "TOPIC_PLATEAU_TRAP",
    "TOPIC_REMEDIATION_CYCLE",
    "TOPIC_REMEDIATION_STEP",
    "TOPIC_SNAPSHOT",
    "TOPIC_WALL_TRIGGERED",
    "latest_for_correlation",
    "publish_adaptation_applied",
    "publish_recovery_metrics",
    "publish_snapshot",
    "publish_wall_triggered",
    "typed_for_correlation",
]
