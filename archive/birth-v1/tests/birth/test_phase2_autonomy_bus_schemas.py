"""Phase 2 Event Bus topic registration smoke tests."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import EVENT_BUS_TOPIC_MODELS
from lumina_core.birth.birth_bus_choreography import (
    TOPIC_PHASE2_GATE_RESULT,
    TOPIC_PHASE2_INSTANCE_PROPOSAL,
    TOPIC_PHASE2_PARAM_PROPOSAL,
    TOPIC_PHASE2_WALL_PROPOSAL,
    publish_phase2_gate_result,
    publish_phase2_instance_proposal,
    publish_phase2_param_proposal,
    publish_phase2_wall_proposal,
)


@pytest.mark.unit
def test_phase2_topics_registered() -> None:
    for topic in (
        TOPIC_PHASE2_WALL_PROPOSAL,
        TOPIC_PHASE2_PARAM_PROPOSAL,
        TOPIC_PHASE2_INSTANCE_PROPOSAL,
        TOPIC_PHASE2_GATE_RESULT,
    ):
        assert topic in EVENT_BUS_TOPIC_MODELS


@pytest.mark.unit
def test_publish_phase2_helpers() -> None:
    bus = EventBus()
    publish_phase2_wall_proposal(
        bus,
        producer="test",
        correlation_id="c1",
        stage="S1",
        proposal={"stall_wall_sec_multiplier": 1.0},
    )
    publish_phase2_param_proposal(
        bus,
        producer="test",
        correlation_id="c1",
        stage="S1",
        proposal={"changes": {}},
    )
    publish_phase2_instance_proposal(
        bus,
        producer="test",
        correlation_id="c1",
        stage="S1",
        proposal={"action": "noop"},
    )
    publish_phase2_gate_result(
        bus,
        producer="test",
        correlation_id="c1",
        stage="S1",
        gate={"allowed": False, "reason": "feature_disabled", "pillar": "dynamic_wall"},
    )
    assert len(bus.history(TOPIC_PHASE2_WALL_PROPOSAL, limit=3)) == 1
    assert len(bus.history(TOPIC_PHASE2_GATE_RESULT, limit=3)) == 1
