"""Soft constitution warnings must not abort; hard violations abort once and stop host."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.agent_orchestration.schemas import ConstitutionViolation
from lumina_core.birth.constitution_enforcer import ConstitutionEnforcer
from lumina_core.birth.curriculum_orchestrator import CurriculumOrchestrator


@pytest.mark.unit
def test_soft_warning_does_not_abort_orchestrator() -> None:
    bus = EventBus()
    orch = CurriculumOrchestrator(bus)
    aborts: list[dict[str, Any]] = []
    orch.on_curriculum_aborted(aborts.append)

    bus.publish_validated(
        topic="safety.constitution.violation",
        producer="test",
        payload=ConstitutionViolation(
            principle_name="birth_constitution_guard",
            severity="warning",
            description="invalid_stop_pct",
            detail="reason=invalid_stop",
            mode="birth",
        ).model_dump(mode="json"),
    )
    assert orch.state.aborted is False
    assert orch.state.constitution_violations_seen == 1
    assert aborts == []


@pytest.mark.unit
def test_hard_critical_aborts_once_and_invokes_callback() -> None:
    bus = EventBus()
    orch = CurriculumOrchestrator(bus)
    aborts: list[dict[str, Any]] = []
    orch.on_curriculum_aborted(aborts.append)

    payload = ConstitutionViolation(
        principle_name="birth_constitution_guard",
        severity="critical",
        description="fatal_rule",
        detail="hard",
        mode="birth",
    ).model_dump(mode="json")
    for _ in range(5):
        bus.publish_validated(
            topic="safety.constitution.violation",
            producer="test",
            payload=payload,
        )
    assert orch.state.aborted is True
    assert len(aborts) == 1
    assert orch.state.constitution_violations_seen == 5


@pytest.mark.unit
def test_enforcer_soft_no_abort_hard_once(tmp_path: Path) -> None:
    bus = EventBus()
    enf = ConstitutionEnforcer(bus)
    enf.attach()
    aborted_topics: list[str] = []

    def _on_abort(event: Any) -> None:
        aborted_topics.append(event.topic)

    bus.subscribe("birth.curriculum.aborted", _on_abort)

    soft = ConstitutionViolation(
        principle_name="birth_constitution_guard",
        severity="warning",
        description="invalid_stop",
        mode="birth",
    ).model_dump(mode="json")
    bus.publish_validated(
        topic="safety.constitution.violation",
        producer="test",
        payload=soft,
    )
    assert enf.is_hard_aborted() is False
    assert aborted_topics == []

    hard = ConstitutionViolation(
        principle_name="no_naked_orders",
        severity="critical",
        description="naked",
        mode="birth",
    ).model_dump(mode="json")
    bus.publish_validated(
        topic="safety.constitution.violation",
        producer="test",
        payload=hard,
    )
    bus.publish_validated(
        topic="safety.constitution.violation",
        producer="test",
        payload=hard,
    )
    assert enf.is_hard_aborted() is True
    assert len(aborted_topics) == 1


@pytest.mark.unit
def test_engine_abort_callback_sets_stop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Host stop path: abort callback forces _stop_requested True."""
    from lumina_core.birth.engine import BirthPhaseEngineV2

    stop = threading.Event()
    # Minimal engine without full runtime wiring failures
    engine = BirthPhaseEngineV2(
        runtime=None,
        workspace_root=tmp_path,
        stop_event=stop,
    )
    assert engine._stop_requested() is False
    engine._on_curriculum_aborted({"reason": "constitution_violation"})
    assert stop.is_set()
    assert engine._stop_requested() is True
    assert engine._force_stop_reason == "constitution_violation"
