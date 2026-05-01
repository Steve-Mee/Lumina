from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus


@pytest.mark.unit
def test_publish_validated_accepts_dream_partial_update() -> None:
    bus = EventBus()
    got: list[object] = []

    def _h(ev) -> None:
        got.append(ev)

    bus.subscribe("trading_engine.dream_state.updated", _h)
    ev = bus.publish_validated(
        topic="trading_engine.dream_state.updated",
        producer="lumina_engine",
        payload={"signal": "BUY", "confidence": 0.82},
    )
    assert ev is not None
    assert len(got) == 1


@pytest.mark.unit
def test_publish_validated_fail_closed_on_bad_types() -> None:
    bus = EventBus()
    got: list[object] = []

    def _h(ev) -> None:
        got.append(ev)

    bus.subscribe("trading_engine.dream_state.updated", _h)
    out = bus.publish_validated(
        topic="trading_engine.dream_state.updated",
        producer="lumina_engine",
        payload={"confidence": "not_a_float"},
    )
    assert out is None
    assert got == []


@pytest.mark.unit
def test_event_bus_publish_and_subscribe() -> None:
    bus = EventBus()
    received: list[dict] = []

    def _handler(event) -> None:
        received.append(event.to_dict())

    bus.subscribe("risk.limit.hit", _handler)
    bus.publish(
        topic="risk.limit.hit",
        producer="risk_controller",
        payload={"limit": "daily_loss", "value": -1500.0},
    )

    assert len(received) == 1
    assert received[0]["topic"] == "risk.limit.hit"
    assert received[0]["producer"] == "risk_controller"
    assert received[0]["payload"]["limit"] == "daily_loss"


@pytest.mark.unit
def test_event_bus_keeps_topic_history() -> None:
    bus = EventBus(max_topic_history=20)
    for idx in range(5):
        bus.publish(
            topic="evolution.candidate.scored",
            producer="evolution_orchestrator",
            payload={"idx": idx},
        )

    history = bus.history("evolution.candidate.scored", limit=3)
    assert len(history) == 3
    assert [item.payload["idx"] for item in history] == [2, 3, 4]
