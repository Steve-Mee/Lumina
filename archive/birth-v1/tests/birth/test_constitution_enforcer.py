"""Tests for ConstitutionEnforcer fail-closed birth abort path."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.constitution_enforcer import ConstitutionEnforcer, TOPIC_ABORTED


@pytest.mark.unit
def test_constitution_enforcer_publishes_abort_on_birth_violation() -> None:
    bus = EventBus()
    enforcer = ConstitutionEnforcer(bus)
    enforcer.attach()

    bus.publish_validated(
        topic="safety.constitution.violation",
        producer="test",
        payload={
            "principle_name": "capital_preservation",
            "severity": "critical",
            "description": "test violation",
            "mode": "birth",
        },
    )

    assert enforcer.violation_count() == 1
    aborted = bus.latest(TOPIC_ABORTED)
    assert aborted is not None
    assert aborted.payload.get("reason") == "constitution_violation"


@pytest.mark.unit
def test_constitution_enforcer_ignores_non_birth_violations() -> None:
    bus = EventBus()
    enforcer = ConstitutionEnforcer(bus)
    enforcer.attach()

    bus.publish_validated(
        topic="safety.constitution.violation",
        producer="test",
        payload={
            "principle_name": "capital_preservation",
            "severity": "critical",
            "description": "real mode violation",
            "mode": "real",
        },
    )

    assert enforcer.violation_count() == 0
    assert bus.latest(TOPIC_ABORTED) is None


@pytest.mark.unit
def test_constitution_enforcer_detach_idempotent() -> None:
    bus = EventBus()
    enforcer = ConstitutionEnforcer(bus)
    enforcer.attach()
    enforcer.detach()
    enforcer.detach()
    assert enforcer._token is None


@pytest.mark.unit
def test_constitution_enforcer_soft_throttle_every_500() -> None:
    bus = EventBus()
    enforcer = ConstitutionEnforcer(bus)
    enforcer.attach()
    for _ in range(500):
        bus.publish_validated(
            topic="safety.constitution.violation",
            producer="test",
            payload={
                "principle_name": "birth_constitution_guard",
                "severity": "warning",
                "description": "risk_exceeds_1pct",
                "mode": "birth",
            },
        )
    # first 3 + 500th (caplog is flaky under coverage/xdist; assert emission counter)
    assert enforcer._soft_warn_emissions == 4
    assert enforcer._soft_logged == 500
    assert enforcer.violation_count() == 500
    assert bus.latest(TOPIC_ABORTED) is None
