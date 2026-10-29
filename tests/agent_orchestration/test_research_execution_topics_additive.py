"""S0 execution topics are additive; existing Event Bus contracts stay unchanged."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import (
    CRITICAL_EVENT_BUS_TOPICS,
    EVENT_BUS_TOPIC_MODELS,
    RESEARCH_EXECUTION_FILL_TOPIC,
    RESEARCH_EXECUTION_ORDER_TOPIC,
    RESEARCH_EXECUTION_SIGNAL_TOPIC,
    RESEARCH_HYPOTHESIS_TOPIC,
    RESEARCH_PROMOTION_TOPIC,
)
from lumina_core.agent_orchestration.schemas_research import EVENT_BUS_GUARDED_TOPICS
from lumina_core.agent_orchestration.schemas_research_execution import (
    FILL_TRANSLATOR_AGENT_ID,
    RESEARCH_BRIDGE_AGENT_ID,
    RESEARCH_EXECUTION_TOPIC_PRODUCERS,
    ResearchExecutionOrderIntent,
    SignalIntent,
)
from lumina_core.engine.agent_blackboard_types import DEFAULT_ALLOWED_PRODUCERS


@pytest.mark.unit
def test_execution_topics_are_registered_additively() -> None:
    assert RESEARCH_HYPOTHESIS_TOPIC in EVENT_BUS_TOPIC_MODELS
    assert RESEARCH_PROMOTION_TOPIC in EVENT_BUS_TOPIC_MODELS
    assert EVENT_BUS_TOPIC_MODELS[RESEARCH_EXECUTION_SIGNAL_TOPIC] is SignalIntent
    assert EVENT_BUS_TOPIC_MODELS[RESEARCH_EXECUTION_ORDER_TOPIC] is ResearchExecutionOrderIntent
    assert RESEARCH_EXECUTION_SIGNAL_TOPIC in CRITICAL_EVENT_BUS_TOPICS
    assert RESEARCH_EXECUTION_ORDER_TOPIC in CRITICAL_EVENT_BUS_TOPICS
    assert RESEARCH_EXECUTION_FILL_TOPIC in CRITICAL_EVENT_BUS_TOPICS
    assert RESEARCH_EXECUTION_SIGNAL_TOPIC in EVENT_BUS_GUARDED_TOPICS
    assert DEFAULT_ALLOWED_PRODUCERS[RESEARCH_EXECUTION_SIGNAL_TOPIC] == {RESEARCH_BRIDGE_AGENT_ID}
    assert DEFAULT_ALLOWED_PRODUCERS[RESEARCH_EXECUTION_FILL_TOPIC] == {
        RESEARCH_BRIDGE_AGENT_ID,
        FILL_TRANSLATOR_AGENT_ID,
    }
    assert RESEARCH_EXECUTION_TOPIC_PRODUCERS[RESEARCH_EXECUTION_FILL_TOPIC] == frozenset(
        {RESEARCH_BRIDGE_AGENT_ID, FILL_TRANSLATOR_AGENT_ID}
    )


@pytest.mark.unit
def test_existing_critical_topic_still_forbids_unknown_fields() -> None:
    bus = EventBus()
    with pytest.raises(ValidationError):
        bus.publish(
            topic="risk.policy.decision",
            producer="risk_controller",
            payload={"approved": True, "novel_untyped_field": "blocked"},
        )


@pytest.mark.unit
def test_admitted_cannot_be_true_on_s0_order_intent() -> None:
    with pytest.raises(ValidationError):
        ResearchExecutionOrderIntent.model_validate(
            {
                "strategy_id": "hyp-s0",
                "config_id": "cfg-s0",
                "trial_id": 1,
                "instrument": "MES",
                "direction": "BUY",
                "size": 1.0,
                "timestamp": "2026-10-28T12:00:00+00:00",
                "expected_horizon": 8,
                "validation_mac": "a" * 64,
                "issue_mac": "b" * 64,
                "admitted": True,
            }
        )
