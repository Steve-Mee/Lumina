from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.agent_orchestration.engine_bindings import bind_engine_event_bus
from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC


@pytest.mark.unit
def test_execution_handler_uses_typed_aggregate_payload() -> None:
    bus = EventBus()
    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="paper"))
    engine.set_current_dream_fields = MagicMock()

    bind_engine_event_bus(engine, bus)
    bus.publish(
        topic=TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
        producer="test",
        payload={"signal": "BUY", "confidence": 0.91, "confluence_score": 0.91},
    )

    engine.set_current_dream_fields.assert_called_once()
    fields = engine.set_current_dream_fields.call_args[0][0]
    assert fields["signal"] == "BUY"
    assert fields["confidence"] == pytest.approx(0.91)
