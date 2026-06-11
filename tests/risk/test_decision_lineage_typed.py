from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.risk.decision_lineage import (
    decision_context_id_from_blackboard_event,
    decision_context_id_from_event,
    event_hash_from_event,
    _fingerprint,
    _payload_dict_from_event,
    get_core_risk_decision_chain,
    is_chain_healthy,
    reconstruct_risk_decision_chain,
)


@pytest.mark.unit
def test_reconstruct_core_chain_uses_typed_payload_models() -> None:
    bus = EventBus()
    ctx = "lineage-typed-ctx-001"

    bus.publish(
        topic="admission.gate_entry",
        producer="order_gatekeeper",
        payload={
            "decision_context_id": ctx,
            "symbol": "MES",
            "proposed_risk": 50.0,
            "mode": "paper",
            "order_side": "BUY",
        },
        metadata={"decision_context_id": ctx, "sequence": 1},
    )
    gate_event = bus.latest("admission.gate_entry")
    assert gate_event is not None
    gate_hash = _fingerprint(gate_event)

    bus.publish(
        topic="risk.policy.decision",
        producer="risk_policy_step",
        payload={"approved": True, "max_risk_percent_multiplier": 1.0},
        metadata={"decision_context_id": ctx, "sequence": 2, "prev_hash": gate_hash},
    )
    policy_event = bus.latest("risk.policy.decision")
    assert policy_event is not None
    policy_hash = _fingerprint(policy_event)

    bus.publish(
        topic="risk.final_arbitration.result",
        producer="final_arbitration",
        payload={"status": "APPROVED", "reason": "ok", "checks": []},
        metadata={"decision_context_id": ctx, "sequence": 3, "prev_hash": policy_hash},
    )

    chain = reconstruct_risk_decision_chain(ctx, event_bus=bus)
    assert len(chain) == 3
    assert all(n.get("hash_ok") for n in chain)
    assert is_chain_healthy(chain)

    gate_node = next(n for n in chain if n["topic"] == "admission.gate_entry")
    assert gate_node.get("payload_model") == "GateEntryPayload"
    assert gate_node["payload"]["symbol"] == "MES"

    arb_node = next(n for n in chain if n["topic"] == "risk.final_arbitration.result")
    assert arb_node.get("payload_model") == "FinalArbitrationResult"
    assert arb_node["payload"]["status"] == "APPROVED"

    core = get_core_risk_decision_chain(ctx, event_bus=bus)
    assert len(core) == 3


@pytest.mark.unit
def test_decision_context_id_from_typed_fill_payload() -> None:
    bus = EventBus()
    ctx = "lineage-fill-ctx-002"
    bus.publish(
        topic="execution.fill.received",
        producer="paper_broker",
        payload={
            "decision_context_id": ctx,
            "fill_id": "f1",
            "symbol": "MES",
            "side": "BUY",
            "quantity": 1,
            "price": 5000.0,
            "timestamp": "2026-06-04T12:00:00Z",
        },
        metadata={"decision_context_id": ctx},
    )
    event = bus.latest("execution.fill.received")
    assert event is not None
    assert decision_context_id_from_event(event) == ctx
    payload, model_name = _payload_dict_from_event(event)
    assert model_name == "ExecutionFill"
    assert payload["fill_id"] == "f1"

    chain = reconstruct_risk_decision_chain(ctx, event_bus=bus)
    assert len(chain) == 1
    assert chain[0]["payload_model"] == "ExecutionFill"


@pytest.mark.unit
def test_event_hash_from_metadata_or_attribute() -> None:
    bus = EventBus()
    bus.publish(
        topic="agent.rl.proposal",
        producer="test",
        payload={"signal": "BUY", "confidence": 0.5},
        metadata={"event_hash": "meta-hash-1"},
    )
    ev = bus.latest("agent.rl.proposal")
    assert ev is not None
    assert event_hash_from_event(ev) == "meta-hash-1"


@pytest.mark.unit
def test_blackboard_correlation_id_fallback() -> None:
    class _BbEvent:
        correlation_id = "corr-fallback-99"
        metadata = {}
        payload = {}
        topic = "agent.rl.proposal"

    assert decision_context_id_from_blackboard_event(_BbEvent()) == "corr-fallback-99"
