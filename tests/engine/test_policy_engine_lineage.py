from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import FinalArbitrationResult
from lumina_core.broker.broker_bridge import Order, OrderResult
from lumina_core.engine.policy_engine import PolicyEngine
from lumina_core.order_gatekeeper import _domain_event_fingerprint


def _arb_event(*, ctx: str, symbol: str = "MES") -> object:
    bus = EventBus()
    bus.publish(
        topic="risk.final_arbitration.result",
        producer="test",
        payload={"status": "APPROVED", "reason": "ok", "checks": []},
        metadata={"symbol": symbol, "decision_context_id": ctx},
        payload_model=FinalArbitrationResult,
    )
    return bus.latest("risk.final_arbitration.result")


@pytest.mark.unit
def test_execute_order_recovers_ctx_from_typed_arb_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    arb = _arb_event(ctx="policy-ctx-meta-001")
    bus = MagicMock()
    bus.history.return_value = [arb]

    broker = MagicMock()
    broker.submit_order.return_value = OrderResult(accepted=True, order_id="1", status="filled", message="ok")

    engine = SimpleNamespace(event_bus=bus, blackboard=None)
    monkeypatch.setattr(
        "lumina_core.engine.policy_engine.enforce_pre_trade_gate",
        lambda *a, **k: (True, "ok"),
    )

    order = Order(symbol="MES", side="BUY", quantity=1, order_type="MARKET")
    policy = PolicyEngine(engine=engine, broker=broker)
    policy.execute_order(order)

    assert order.metadata.get("decision_context_id") == "policy-ctx-meta-001"
    assert order.metadata.get("prev_hash") == _domain_event_fingerprint(arb)
    assert order.metadata.get("prev_event_topic") == "risk.final_arbitration.result"


@pytest.mark.unit
def test_execute_order_uses_latest_arb_for_matching_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    bus_real = EventBus()
    bus_real.publish(
        topic="risk.final_arbitration.result",
        producer="test",
        payload={"status": "APPROVED", "reason": "old", "checks": []},
        metadata={"symbol": "MES", "decision_context_id": "policy-ctx-old"},
        payload_model=FinalArbitrationResult,
    )
    bus_real.publish(
        topic="risk.final_arbitration.result",
        producer="test",
        payload={"status": "APPROVED", "reason": "new", "checks": []},
        metadata={"symbol": "MES", "decision_context_id": "policy-ctx-new"},
        payload_model=FinalArbitrationResult,
    )
    history = list(bus_real.history("risk.final_arbitration.result", limit=20))
    arb_new = history[-1]

    bus = MagicMock()
    bus.history.side_effect = [history, [arb_new]]

    broker = MagicMock()
    broker.submit_order.return_value = OrderResult(accepted=True, order_id="1", status="filled", message="ok")

    engine = SimpleNamespace(event_bus=bus, blackboard=None)
    monkeypatch.setattr(
        "lumina_core.engine.policy_engine.enforce_pre_trade_gate",
        lambda *a, **k: (True, "ok"),
    )

    order = Order(symbol="MES", side="BUY", quantity=1, order_type="MARKET")
    policy = PolicyEngine(engine=engine, broker=broker)
    policy.execute_order(order)

    assert order.metadata.get("decision_context_id") == "policy-ctx-new"


@pytest.mark.unit
def test_execute_order_skips_lineage_when_gate_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = MagicMock()
    engine = SimpleNamespace(event_bus=MagicMock(), blackboard=None)
    monkeypatch.setattr(
        "lumina_core.engine.policy_engine.enforce_pre_trade_gate",
        lambda *a, **k: (False, "blocked"),
    )

    order = Order(symbol="MES", side="BUY", quantity=1, order_type="MARKET")
    policy = PolicyEngine(engine=engine, broker=broker)
    result = policy.execute_order(order)

    assert result.accepted is False
    broker.submit_order.assert_not_called()
    engine.event_bus.history.assert_not_called()
