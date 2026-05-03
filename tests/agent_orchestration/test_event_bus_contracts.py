from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.event_bus import EventBus, TradeSignal
from lumina_core.agent_orchestration.schemas import AgentProposalPayload
from lumina_core.engine.agent_blackboard import AgentBlackboard


@pytest.mark.unit
def test_publish_validated_rejects_invalid_typed_payload_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()
    received: list[object] = []

    def _handler(event: object) -> None:
        received.append(event)

    bus.subscribe("risk.policy.decision", _handler)

    out = bus.publish_validated(
        topic="risk.policy.decision",
        producer="risk_controller",
        payload={"max_risk_percent_multiplier": -0.1},
    )

    assert out is None
    assert received == []
    assert "schema violation" in caplog.text
    assert "risk.policy.decision" in caplog.text


@pytest.mark.unit
def test_publish_accepts_legacy_dict_payload_without_contract() -> None:
    bus = EventBus()
    received_payloads: list[dict[str, object]] = []

    def _handler(event: object) -> None:
        payload = getattr(event, "payload", {})
        if isinstance(payload, dict):
            received_payloads.append(payload)

    bus.subscribe("legacy.custom.topic", _handler)
    event = bus.publish(
        topic="legacy.custom.topic",
        producer="legacy_migrator",
        payload={"field": "value", "count": "not_typed"},
    )

    assert event.payload["field"] == "value"
    assert event.payload["count"] == "not_typed"
    assert received_payloads == [{"field": "value", "count": "not_typed"}]


@pytest.mark.unit
def test_publish_typed_topic_without_payload_model_still_validates_and_coerces() -> None:
    bus = EventBus()
    event = bus.publish(
        topic="risk.policy.decision",
        producer="risk_controller",
        payload={"approved": True, "max_risk_percent_multiplier": "0.9"},
    )

    assert event.payload["approved"] is True
    assert isinstance(event.payload["max_risk_percent_multiplier"], float)
    assert event.payload["max_risk_percent_multiplier"] == pytest.approx(0.9)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("topic", "payload"),
    [
        ("trading_engine.trade_signal.emitted", {"signal": "BUY", "confidence": 0.84}),
        ("risk.policy.decision", {"approved": True, "reason": "within_limits"}),
        ("evolution.proposal.created", {"status": "candidate"}),
        ("evolution.shadow.verdict", {"verdict": "pass", "sample_size": 5}),
        ("safety.constitution.audit", {"phase": "promotion", "passed": True, "mode": "REAL"}),
    ],
)
def test_publish_critical_topic_rejects_unknown_top_level_fields_fail_closed(
    topic: str,
    payload: dict[str, object],
) -> None:
    bus = EventBus()

    with pytest.raises(ValidationError):
        bus.publish(
            topic=topic,
            producer="strategy_engine",
            payload={**payload, "novel_untyped_field": "blocked"},
        )


@pytest.mark.unit
def test_publish_dream_state_topic_allows_experimental_extra_fields() -> None:
    bus = EventBus()
    event = bus.publish(
        topic="trading_engine.dream_state.updated",
        producer="lumina_engine",
        payload={
            "signal": "HOLD",
            "confidence": 0.41,
            "fib_levels": {"0.618": 5300.25},
            "emotional_bias": {"tilt_score": 0.12},
        },
    )

    assert event.payload["signal"] == "HOLD"
    assert event.payload["fib_levels"]["0.618"] == pytest.approx(5300.25)
    assert event.payload["emotional_bias"]["tilt_score"] == pytest.approx(0.12)


@pytest.mark.unit
def test_publish_meta_reflection_topic_keeps_experimental_space() -> None:
    bus = EventBus()
    event = bus.publish(
        topic="meta.agent.reflection",
        producer="meta_agent_orchestrator",
        payload={"window_hours": "12", "novel_metric": "kept"},
    )

    assert event.payload["window_hours"] == 12
    assert event.payload["novel_metric"] == "kept"


@pytest.mark.unit
def test_publish_with_payload_model_validates_and_forwards_typed_payload() -> None:
    bus = EventBus()
    received_payloads: list[dict[str, object]] = []

    def _handler(event: object) -> None:
        payload = getattr(event, "payload", {})
        if isinstance(payload, dict):
            received_payloads.append(payload)

    bus.subscribe("trading_engine.trade_signal.emitted", _handler)
    event = bus.publish(
        topic="trading_engine.trade_signal.emitted",
        producer="strategy_engine",
        payload={"signal": "BUY", "confidence": "0.84"},
        payload_model=TradeSignal,
    )

    assert isinstance(event.payload["confidence"], float)
    assert event.payload["confidence"] == pytest.approx(0.84)
    assert received_payloads[0]["signal"] == "BUY"
    assert isinstance(received_payloads[0]["confidence"], float)


@pytest.mark.unit
def test_publish_with_payload_model_raises_validation_error_fail_closed() -> None:
    bus = EventBus()
    received: list[object] = []

    def _handler(event: object) -> None:
        received.append(event)

    bus.subscribe("trading_engine.trade_signal.emitted", _handler)

    with pytest.raises(ValidationError):
        bus.publish(
            topic="trading_engine.trade_signal.emitted",
            producer="strategy_engine",
            payload={"signal": "BUY", "position_size_multiplier": -1.0},
            payload_model=TradeSignal,
        )

    assert received == []


@pytest.mark.unit
def test_blackboard_publish_with_payload_model_validates_and_forwards_typed_payload(
    tmp_path: Path,
) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    received_payloads: list[dict[str, object]] = []

    def _handler(event: object) -> None:
        payload = getattr(event, "payload", {})
        if isinstance(payload, dict):
            received_payloads.append(payload)

    board.subscribe("agent.rl.proposal", _handler)
    event = board.publish_sync(
        topic="agent.rl.proposal",
        producer="rl_policy",
        payload={"signal": "BUY", "confidence": "0.72", "qty": "2"},
        confidence=0.9,
        payload_model=AgentProposalPayload,
    )

    assert isinstance(event.payload["confidence"], float)
    assert isinstance(event.payload["qty"], float)
    assert event.payload["confidence"] == pytest.approx(0.72)
    assert event.payload["qty"] == pytest.approx(2.0)
    assert received_payloads[0]["signal"] == "BUY"


@pytest.mark.unit
def test_blackboard_typed_topic_without_payload_model_still_validates_and_coerces(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    event = board.publish_sync(
        topic="agent.rl.proposal",
        producer="rl_policy",
        payload={"signal": "BUY", "confidence": "0.72", "qty": "2"},
        confidence=0.9,
    )

    assert isinstance(event.payload["confidence"], float)
    assert isinstance(event.payload["qty"], float)
    assert event.payload["confidence"] == pytest.approx(0.72)
    assert event.payload["qty"] == pytest.approx(2.0)


@pytest.mark.unit
def test_blackboard_publish_with_payload_model_rejects_invalid_payload_fail_closed(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    received: list[object] = []

    def _handler(event: object) -> None:
        received.append(event)

    board.subscribe("agent.rl.proposal", _handler)
    with pytest.raises(ValidationError):
        board.publish_sync(
            topic="agent.rl.proposal",
            producer="rl_policy",
            payload={"signal": "BUY", "qty": -0.5},
            confidence=0.88,
            payload_model=AgentProposalPayload,
        )

    assert received == []
