from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import AdaptiveIntelligenceState
from lumina_core.monitoring.adaptive_intelligence_tracker import AdaptiveIntelligenceTracker


@pytest.mark.unit
def test_tracker_persists_latest_and_history(tmp_path: Path) -> None:
    bus = EventBus()
    tracker = AdaptiveIntelligenceTracker(tmp_path)
    tracker.bind(bus)

    payload = AdaptiveIntelligenceState(
        tier="standard",
        mode="auto",
        reasoning_mode="hybrid_balanced",
        degraded_state=False,
        status_reason="auto_hardware_resolution",
        recommended_model="qwen3.5-9b",
        recommended_provider="ollama",
        context_length=16384,
        source="test",
        timestamp="2026-05-18T00:00:00+00:00",
    ).model_dump(mode="json")
    bus.publish(
        topic="inference.adaptive_intelligence.state",
        producer="test_case",
        payload=payload,
        payload_model=AdaptiveIntelligenceState,
    )

    latest = tracker.latest()
    assert isinstance(latest, dict)
    assert latest["payload"]["tier"] == "standard"
    assert latest["producer"] == "test_case"

    history = tracker.history(limit=10)
    assert len(history) == 1
    assert history[0]["payload"]["recommended_provider"] == "ollama"
    print("MANUAL_SMOKE_PHASE2_D3_SLICE5_TYPED_TRACKER_SUCCESS")


@pytest.mark.unit
def test_tracker_deduplicates_identical_state_payloads(tmp_path: Path) -> None:
    bus = EventBus()
    tracker = AdaptiveIntelligenceTracker(tmp_path)
    tracker.bind(bus)

    payload = AdaptiveIntelligenceState(
        tier="light",
        mode="auto",
        reasoning_mode="fast_path_only",
        degraded_state=True,
        status_reason="force_high_requested_but_hardware_insufficient",
        recommended_model="qwen3.5-4b",
        recommended_provider="ollama",
        context_length=8192,
        source="test",
        timestamp="2026-05-18T00:00:00+00:00",
    ).model_dump(mode="json")

    bus.publish(
        topic="inference.adaptive_intelligence.state",
        producer="test_case",
        payload=payload,
        payload_model=AdaptiveIntelligenceState,
    )
    # Same state, only transport metadata differs; should not create extra history row.
    bus.publish(
        topic="inference.adaptive_intelligence.state",
        producer="test_case",
        payload={**payload, "timestamp": "2026-05-18T00:00:01+00:00"},
        payload_model=AdaptiveIntelligenceState,
    )

    history = tracker.history(limit=10)
    assert len(history) == 1


@pytest.mark.unit
def test_tracker_uses_payload_instance_when_present(tmp_path: Path) -> None:
    """Phase 2 D3 slice 5: persistence prefers validated instance over stale raw dict."""
    tracker = AdaptiveIntelligenceTracker(tmp_path)
    model = AdaptiveIntelligenceState(
        tier="high",
        mode="force_high",
        reasoning_mode="deep",
        degraded_state=False,
        status_reason="hardware_ok",
        recommended_model="qwen3.5-27b",
        recommended_provider="ollama",
        context_length=32768,
        source="typed_instance_test",
        timestamp="2026-06-11T00:00:00+00:00",
    )
    event = DomainEvent(
        topic="inference.adaptive_intelligence.state",
        producer="typed_test",
        payload={"tier": "light", "mode": "auto"},
        payload_instance=model,
    )
    tracker._on_event(event)

    latest = tracker.latest()
    assert latest is not None
    assert latest["payload"]["tier"] == "high"
    assert latest["payload"]["recommended_model"] == "qwen3.5-27b"
