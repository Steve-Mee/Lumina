from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import AgentProposalPayload
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from tests.test_order_gatekeeper_contracts import _RiskController, _make_engine


@pytest.mark.unit
def test_slice8_gate_entry_prev_hash_from_typed_proposal_on_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = "gk8-slice8-ctx-001"
    bus = EventBus()
    bus.publish(
        topic="agent.rl.proposal",
        producer="test_rl",
        payload={"signal": "BUY", "confidence": 0.9, "decision_context_id": ctx},
        metadata={"decision_context_id": ctx, "event_hash": "proposal-hash-gk8"},
        payload_model=AgentProposalPayload,
    )

    class _BbWithCtx:
        def latest(self, topic: str):
            if topic == "agent.rl.proposal":
                return SimpleNamespace(
                    correlation_id=ctx,
                    metadata={"decision_context_id": ctx},
                    payload={"decision_context_id": ctx},
                    topic=topic,
                )
            return None

    engine = _make_engine(trade_mode="paper", risk_controller=_RiskController(can_trade=True, reason="OK"))
    engine.event_bus = bus
    engine.blackboard = _BbWithCtx()
    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)

    allowed, _ = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=48.0,
        order_side="BUY",
    )
    assert allowed is True

    gate_entries = list(bus.history("admission.gate_entry", limit=10))
    assert gate_entries
    matching = [e for e in gate_entries if e.metadata.get("decision_context_id") == ctx]
    assert matching, "expected gate_entry for proposal ctx"
    assert matching[-1].metadata.get("prev_hash") == "proposal-hash-gk8"
