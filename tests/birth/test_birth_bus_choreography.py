"""Tests for birth EventBus choreography helpers."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import BirthAdaptationApplied, BirthStageRolloutSnapshot
from lumina_core.birth.birth_bus_choreography import (
    TOPIC_ADAPTATION_APPLIED,
    TOPIC_SNAPSHOT,
    latest_for_correlation,
    publish_adaptation_applied,
    publish_snapshot,
    typed_for_correlation,
)


@pytest.mark.unit
def test_publish_snapshot_sets_correlation_metadata() -> None:
    bus = EventBus()
    event = publish_snapshot(
        bus,
        producer="test",
        correlation_id="cid-abc",
        signal="meta_observe",
        stage="stage1_trend",
        context={"stage_trades": 10},
    )
    assert event.topic == TOPIC_SNAPSHOT
    assert event.metadata.get("correlation_id") == "cid-abc"
    assert bus.latest(TOPIC_SNAPSHOT) is not None


@pytest.mark.unit
def test_latest_for_correlation_matches_payload_cid() -> None:
    bus = EventBus()
    publish_snapshot(
        bus,
        producer="test",
        correlation_id="cid-1",
        signal="meta_observe",
        stage="stage1_trend",
        context={},
    )
    publish_snapshot(
        bus,
        producer="test",
        correlation_id="cid-2",
        signal="meta_decide",
        stage="stage1_trend",
        context={},
    )
    found = latest_for_correlation(bus, TOPIC_SNAPSHOT, "cid-1")
    assert found is not None
    assert found.payload.get("correlation_id") == "cid-1"


@pytest.mark.unit
def test_latest_for_correlation_returns_none_when_missing() -> None:
    bus = EventBus()
    assert latest_for_correlation(bus, TOPIC_SNAPSHOT, "missing") is None


@pytest.mark.unit
def test_typed_for_correlation_returns_model() -> None:
    bus = EventBus()
    publish_snapshot(
        bus,
        producer="test",
        correlation_id="cid-typed",
        signal="meta_observe",
        stage="stage1_trend",
        context={"stage_trades": 42},
    )
    typed = typed_for_correlation(
        bus,
        TOPIC_SNAPSHOT,
        "cid-typed",
        BirthStageRolloutSnapshot,
    )
    assert typed is not None
    assert typed.correlation_id == "cid-typed"
    assert typed.context["stage_trades"] == 42


@pytest.mark.unit
def test_publish_adaptation_applied_roundtrip() -> None:
    bus = EventBus()
    publish_adaptation_applied(
        bus,
        producer="test",
        correlation_id="cid-adapt",
        stage="stage1_trend",
        reason="stall_escalation",
        adaptation_tier=1,
        retries_this_stage=2,
        chunk_target=16,
        escalation_level=1,
        parameter_patch={"winrate_window": 14},
        dispatch="continue_loop",
        recovery_kind="adaptive",
    )
    event = latest_for_correlation(bus, TOPIC_ADAPTATION_APPLIED, "cid-adapt")
    assert event is not None
    applied = event.typed_payload(BirthAdaptationApplied)
    assert applied.recovery_kind == "adaptive"
    assert applied.chunk_target == 16
