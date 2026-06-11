from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.agent_orchestration.schemas import AgentProposalPayload
from lumina_core.engine.agent_blackboard import AgentBlackboard, BlackboardEvent


def test_blackboard_publish_subscribe_and_persistence(tmp_path: Path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")

    seen = []

    def _handler(event) -> None:
        seen.append((event.topic, event.payload.get("signal")))

    token = bus.subscribe("agent.rl.proposal", _handler)
    event = bus.publish_sync(
        topic="agent.rl.proposal",
        producer="test",
        payload={"signal": "BUY", "qty": 1},
        confidence=0.91,
    )

    assert event.event_hash
    assert seen == [("agent.rl.proposal", "BUY")]

    lines = (tmp_path / "blackboard.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    bus.unsubscribe(token)
    bus.publish_sync(
        topic="agent.rl.proposal",
        producer="test",
        payload={"signal": "SELL", "qty": 1},
        confidence=0.95,
    )
    assert seen == [("agent.rl.proposal", "BUY")]


def test_blackboard_history_filtering(tmp_path: Path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")

    bus.publish_sync(
        topic="agent.rl.proposal",
        producer="rl_policy",
        payload={"signal": "BUY", "qty": 1.0},
        confidence=0.85,
    )
    bus.publish_sync(
        topic="agent.rl.proposal",
        producer="rl_policy",
        payload={"signal": "HOLD", "qty": 1.0},
        confidence=0.75,
    )

    hist = bus.history("agent.rl.proposal", limit=10, within_hours=24)
    assert len(hist) == 2
    assert hist[-1].payload["signal"] == "HOLD"


def test_blackboard_rejects_unauthorized_producer(tmp_path: Path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")

    with pytest.raises(PermissionError):
        bus.publish_sync(
            topic="agent.news.proposal",
            producer="rogue_agent",
            payload={"signal": "BUY"},
            confidence=0.9,
        )


def test_blackboard_noncritical_topic_drops_on_full_queue(tmp_path: Path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    _token, queue = bus.subscribe_async("market.tape", maxsize=1)

    first = bus.publish_sync(
        topic="market.tape",
        producer="market_data_service",
        payload={"signal": "BUY"},
        confidence=0.6,
    )
    second = bus.publish_sync(
        topic="market.tape",
        producer="market_data_service",
        payload={"signal": "SELL"},
        confidence=0.7,
    )

    assert queue.qsize() == 1
    assert first.sequence == 1
    assert second.sequence == 2


def test_blackboard_critical_topic_fails_on_full_queue(tmp_path: Path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    _token, _queue = bus.subscribe_async("agent.rl.proposal", maxsize=1)

    bus.publish_sync(
        topic="agent.rl.proposal",
        producer="rl_policy",
        payload={"signal": "BUY", "qty": 1.0},
        confidence=0.9,
    )
    with pytest.raises(RuntimeError):
        bus.publish_sync(
            topic="agent.rl.proposal",
            producer="rl_policy",
            payload={"signal": "SELL", "qty": 1.0},
            confidence=0.92,
        )


@pytest.mark.unit
def test_blackboard_to_dict_canonicalizes_payload_from_instance() -> None:
    """Phase 2 D3 slice 6: JSONL export uses validated instance, not stale raw dict."""
    model = AgentProposalPayload(signal="BUY", confidence=0.72, qty=2.0)
    event = BlackboardEvent(
        topic="agent.rl.proposal",
        producer="rl_policy",
        payload={"signal": "HOLD", "confidence": 0.1, "qty": 0.0},
        confidence=0.9,
        timestamp="2026-06-11T00:00:00+00:00",
        correlation_id="ctx-1",
        payload_instance=model,
    )
    exported = event.to_dict()
    assert exported["payload"]["signal"] == "BUY"
    assert exported["payload_instance"] == exported["payload"]
    assert exported["payload_model"] == "AgentProposalPayload"


@pytest.mark.unit
def test_blackboard_jsonl_persists_typed_export_fields(tmp_path: Path) -> None:
    board = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    board.publish_sync(
        topic="agent.rl.proposal",
        producer="rl_policy",
        payload={"signal": "BUY", "confidence": "0.72", "qty": "2"},
        confidence=0.9,
    )
    row = json.loads((tmp_path / "blackboard.jsonl").read_text(encoding="utf-8").strip())
    assert row["payload_model"] == "AgentProposalPayload"
    assert row["payload"]["signal"] == "BUY"
    assert row["payload_instance"] == row["payload"]
    print("MANUAL_SMOKE_PHASE2_D3_SLICE6_BLACKBOARD_JSONL_TYPED_SUCCESS")
