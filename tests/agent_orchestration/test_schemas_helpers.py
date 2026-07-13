"""Unit tests for agent_orchestration schema helper functions."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import (
    RiskVerdict,
    filter_payload_for_execution_aggregate,
    is_schema_violation,
    typed_payload_from_event,
    validate_payload_with_model,
    validate_registered_event_payload,
)


class _SampleModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int


@pytest.mark.unit
def test_validate_payload_with_model_roundtrip() -> None:
    result = validate_payload_with_model(payload={"value": 42}, payload_model=_SampleModel)
    assert result["value"] == 42


@pytest.mark.unit
def test_validate_registered_event_payload_risk_topic() -> None:
    payload = validate_registered_event_payload(
        "risk.policy.decision",
        {"max_risk_percent_multiplier": 1.0, "approved": True},
    )
    assert payload.get("approved") is True


@pytest.mark.unit
def test_validate_registered_event_payload_unknown_topic_passthrough() -> None:
    raw = {"custom": True}
    assert validate_registered_event_payload("legacy.custom.topic", raw) == raw


@pytest.mark.unit
def test_is_schema_violation_detects_validation_error() -> None:
    try:
        _SampleModel.model_validate({"value": "bad"})
    except ValidationError as exc:
        assert is_schema_violation(exc) is True
    assert is_schema_violation(ValueError("other")) is False


@pytest.mark.unit
def test_typed_payload_from_event_domain_event() -> None:
    bus = EventBus()
    event = bus.publish(
        topic="risk.policy.decision",
        producer="test",
        payload={"max_risk_percent_multiplier": 1.0, "approved": True},
    )
    typed = typed_payload_from_event(event, RiskVerdict)
    assert typed.approved is True


@pytest.mark.unit
def test_typed_payload_from_event_plain_dict() -> None:
    event = DomainEvent(
        topic="test",
        producer="test",
        payload={"max_risk_percent_multiplier": 0.5, "approved": False},
    )
    typed = typed_payload_from_event(event, RiskVerdict)
    assert typed.approved is False


@pytest.mark.unit
def test_filter_payload_for_execution_aggregate_strips_unknown() -> None:
    filtered = filter_payload_for_execution_aggregate(
        {
            "signal": "BUY",
            "confidence": 0.8,
            "unexpected_field": "drop-me",
        }
    )
    assert "unexpected_field" not in filtered
    assert filtered.get("signal") == "BUY"
