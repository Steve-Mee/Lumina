"""Expanded OrganismAutonomyHandler EventBus integration tests."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.organism_autonomy import RecoveryDispatch


@pytest.mark.unit
def test_autonomy_handler_evaluates_terminal_stall() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(autonomous_recovery_enabled=True, phoenix_loop_enabled=True)
    reward = BirthRewardConfig()
    client = BirthBusClient(bus, cfg, reward)

    decision = client.autonomy_evaluate_terminal_stall(
        CurriculumStage.STAGE1_TREND,
        pending={"terminal_stall_reason": "stall_remediation_exhausted"},
        stage_trades=500,
        required=600,
        constitution_violations=0,
        fitness_signal=0.38,
        remediation_cycles_exhausted=True,
        plateau_exhausted=True,
    )
    assert decision.dispatch in {
        RecoveryDispatch.PHOENIX_RESUME,
        RecoveryDispatch.CONTINUE_LOOP,
        RecoveryDispatch.TERMINAL_NOTIFY_ONLY,
    }
    assert bus.latest("birth.autonomy.decision") is not None


@pytest.mark.unit
def test_autonomy_handler_restore_and_get_state() -> None:
    bus = EventBus()
    client = BirthBusClient(
        bus,
        BirthCurriculumConfig(autonomous_recovery_enabled=True),
        BirthRewardConfig(),
    )
    metrics = {
        "autonomous_recovery_count": 7,
        "last_recommended_action": "expand_data",
        "phoenix_count": 2,
    }
    cid_restore = client.emit(
        "autonomy_restore_state", CurriculumStage.STAGE1_TREND, {"metrics": metrics}
    )
    client.registry.pop_response(cid_restore)
    cid_get = client.emit("autonomy_get_state", CurriculumStage.STAGE1_TREND, {})
    resp = client.registry.pop_response(cid_get)
    assert resp["state"]["autonomous_recovery_count"] == 7
    assert resp["state"]["last_recommended_action"] == "expand_data"


@pytest.mark.unit
def test_autonomy_handler_patch_state() -> None:
    bus = EventBus()
    client = BirthBusClient(bus, BirthCurriculumConfig(), BirthRewardConfig())
    cid = client.emit(
        "autonomy_patch_state",
        CurriculumStage.STAGE1_TREND,
        {"last_recommended_action": "phoenix_reset", "autonomous_recovery_count": 3},
    )
    resp = client.registry.pop_response(cid)
    assert resp.get("ok") is True
    assert client.autonomy_state.last_recommended_action == "phoenix_reset"
    assert client.autonomy_state.autonomous_recovery_count == 3


@pytest.mark.unit
def test_autonomy_handler_ignores_invalid_snapshot(birth_bus_client: BirthBusClient) -> None:
    from lumina_core.agent_orchestration.event_bus import DomainEvent

    handler = birth_bus_client.registry.autonomy
    handler._on_snapshot(
        DomainEvent(
            topic="birth.stage.rollout.snapshot",
            producer="test",
            payload={"signal": "autonomy_evaluate_terminal_stall"},
        )
    )
    assert birth_bus_client.bus.latest("birth.autonomy.decision") is None
