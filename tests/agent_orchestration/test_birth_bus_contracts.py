"""Event bus contract tests for birth orchestration schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.event_bus import EventBus


@pytest.mark.unit
@pytest.mark.parametrize(
    "topic,payload",
    [
        (
            "birth.stage.rollout.snapshot",
            {
                "correlation_id": "cid-1",
                "signal": "meta_observe",
                "stage": "stage1_trend",
                "context": {"stage_trades": 10},
            },
        ),
        (
            "birth.meta.plan",
            {
                "correlation_id": "cid-1",
                "trigger": "periodic",
                "plan": {"primary": "hold"},
            },
        ),
        (
            "birth.plateau.evolution.step",
            {
                "stage": "stage1_trend",
                "evolution_step": 1,
                "action": "expand_data",
            },
        ),
        (
            "birth.plateau.trap.detected",
            {
                "stage": "stage2_range",
                "detected": True,
                "range_flat_ratio": 0.1,
                "range_round_trips": 12,
            },
        ),
        (
            "birth.stall.remediation.cycle",
            {"cycle": 1, "max_cycles": 3, "winrate_at_start": 0.35},
        ),
        (
            "birth.stall.remediation.step",
            {"cycle": 1, "step": 1, "max_steps": 5, "action": "expand_and_retry"},
        ),
        (
            "birth.autonomy.decision",
            {
                "dispatch": "continue_loop",
                "stall_reason": "stage_stalled",
                "message": "ok",
            },
        ),
        (
            "birth.certificate.remediation.requested",
            {
                "progress_snapshot": {"phase": "certificate_failed"},
                "checkpoint_state": {},
                "fast_path_eligible": True,
            },
        ),
        (
            "birth.wall.triggered",
            {
                "correlation_id": "cid-wall",
                "stage": "stage1_trend",
                "trigger_type": "certified_stall",
                "failure_key": "stage1_winrate",
                "elapsed_stage_sec": 400.0,
                "constitution_violations": 0,
            },
        ),
        (
            "birth.adaptation.applied",
            {
                "correlation_id": "cid-adapt",
                "stage": "stage1_trend",
                "reason": "metrics_not_improving_within_wall",
                "adaptation_tier": 0,
                "retries_this_stage": 1,
                "chunk_target": 8,
                "escalation_level": 1,
                "dispatch": "continue_loop",
            },
        ),
        (
            "birth.autonomy.recovery.metrics",
            {
                "stage": "stage1_trend",
                "wall_triggers_total": 1,
                "recovery_attempts": 1,
                "recovery_successes": 1,
                "autonomous_recovery_rate_pct": 100.0,
            },
        ),
    ],
)
def test_birth_orchestration_topics_round_trip(topic: str, payload: dict[str, object]) -> None:
    bus = EventBus()
    received: list[dict[str, object]] = []

    def _handler(event: object) -> None:
        p = getattr(event, "payload", {})
        if isinstance(p, dict):
            received.append(p)

    bus.subscribe(topic, _handler)
    bus.publish(topic=topic, producer="test", payload=payload)
    assert received
    if "correlation_id" in payload:
        assert received[0].get("correlation_id") == payload["correlation_id"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "topic,payload",
    [
        (
            "birth.curriculum.stage.completed",
            {
                "stage": "stage1_trend",
                "passed": True,
                "trades": 500,
                "wins": 200,
                "hold_ratio": 0.1,
                "provisional": False,
                "message": "ok",
            },
        ),
        (
            "birth.curriculum.aborted",
            {
                "stage": "stage1_trend",
                "reason": "constitution_violation",
                "detail": {"principle_name": "test"},
                "violations": 1,
            },
        ),
    ],
)
def test_birth_curriculum_critical_topics_round_trip(topic: str, payload: dict[str, object]) -> None:
    bus = EventBus()
    bus.publish_validated(topic=topic, producer="test", payload=payload)
    latest = bus.latest(topic)
    assert latest is not None
    assert latest.payload.get("stage") == payload.get("stage")


@pytest.mark.unit
def test_birth_curriculum_completed_rejects_invalid_payload() -> None:
    bus = EventBus()
    with pytest.raises(ValidationError):
        bus.publish_validated(
            topic="birth.curriculum.stage.completed",
            producer="test",
            payload={"stage": "stage1_trend", "passed": True, "trades": -1, "wins": 0, "hold_ratio": 0.0},
        )
