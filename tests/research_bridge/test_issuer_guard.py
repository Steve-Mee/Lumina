"""Only research_bridge may publish research.execution topics."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas_research import HYPOTHESIS_AGENT_ID
from lumina_core.agent_orchestration.schemas_research_execution import (
    FILL_TRANSLATOR_AGENT_ID,
    RESEARCH_BRIDGE_AGENT_ID,
    RESEARCH_EXECUTION_FILL_TOPIC,
    RESEARCH_EXECUTION_ORDER_TOPIC,
    RESEARCH_EXECUTION_SIGNAL_TOPIC,
    ResearchExecutionFill,
    SignalIntent,
)
from tests.research_bridge.helpers import make_runtime, sealed_candidate


def _signal_payload() -> dict[str, object]:
    return SignalIntent(
        strategy_id="hyp-s0",
        config_id="cfg-s0",
        trial_id=1,
        instrument="MES",
        direction="BUY",
        size=1.0,
        timestamp=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        expected_horizon=8,
        validation_mac="a" * 64,
        issue_mac="b" * 64,
    ).model_dump(mode="json")


@pytest.mark.unit
def test_hypothesis_agent_cannot_publish_signal_intent() -> None:
    bus = EventBus()
    with pytest.raises(PermissionError):
        bus.publish(
            topic=RESEARCH_EXECUTION_SIGNAL_TOPIC,
            producer=HYPOTHESIS_AGENT_ID,
            payload=_signal_payload(),
        )


@pytest.mark.unit
def test_fill_translator_cannot_publish_signal_or_order() -> None:
    bus = EventBus()
    payload = _signal_payload()
    with pytest.raises(PermissionError):
        bus.publish(topic=RESEARCH_EXECUTION_SIGNAL_TOPIC, producer=FILL_TRANSLATOR_AGENT_ID, payload=payload)
    with pytest.raises(PermissionError):
        bus.publish(topic=RESEARCH_EXECUTION_ORDER_TOPIC, producer=FILL_TRANSLATOR_AGENT_ID, payload=payload)


@pytest.mark.unit
def test_research_bridge_publishes_after_guard_is_registered(tmp_path: Path) -> None:
    bus, authority, runtime, _alerts, _observe = make_runtime(tmp_path, healthy=True)
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is not None
    signals = bus.history(RESEARCH_EXECUTION_SIGNAL_TOPIC, limit=10)
    orders = bus.history(RESEARCH_EXECUTION_ORDER_TOPIC, limit=10)
    fills = bus.history(RESEARCH_EXECUTION_FILL_TOPIC, limit=10)
    assert len(signals) == 1
    assert signals[0].producer == RESEARCH_BRIDGE_AGENT_ID
    assert len(orders) == 1
    assert orders[0].payload["admitted"] is False
    assert len(fills) == 1
    assert fills[0].payload["source"] == "hypothetical_adr0055"
    typed = ResearchExecutionFill.model_validate(fills[0].payload)
    assert typed.fill_price == typed.price
    assert typed.qty == typed.quantity


@pytest.mark.unit
def test_research_bridge_without_runtime_guard_is_rejected() -> None:
    bus = EventBus()
    with pytest.raises(PermissionError, match="issuer guard"):
        bus.publish(
            topic=RESEARCH_EXECUTION_SIGNAL_TOPIC,
            producer=RESEARCH_BRIDGE_AGENT_ID,
            payload=_signal_payload(),
        )
