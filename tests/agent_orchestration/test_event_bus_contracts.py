from __future__ import annotations

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.event_bus import EventBus, TradeSignal


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
