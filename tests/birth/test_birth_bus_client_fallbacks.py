"""BirthBusClient fallback branches when handler responses are empty."""

from __future__ import annotations


import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_client import BirthBusClient, _hold_plan
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import LearningSnapshot


@pytest.mark.unit
def test_hold_plan_default_snapshot() -> None:
    plan = _hold_plan(None)
    assert plan.rationale == "bus_no_response"


@pytest.mark.unit
def test_birth_bus_client_fallback_paths_when_responses_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(meta_controller_enabled=True)
    client = BirthBusClient(bus, cfg, BirthRewardConfig())
    monkeypatch.setattr(client.registry, "pop_response", lambda _cid: {})

    stage = CurriculumStage.STAGE1_TREND
    snap = LearningSnapshot(
        winrate_history=(0.3,),
        reward_history=(0.1,),
        stage_trades=10,
        required_trades=100,
        patterns_mined=0,
        patterns_last_inject=0,
        oracle_wins_last_inject=0,
        buffer_size=0,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=0,
        data_exhausted=False,
        stage=stage,
        intra_hard_pct=None,
    )

    observed, stall = client.meta_observe(
        stage,
        winrate_history=[0.3],
        reward_history=[0.1],
        stage_trades=10,
        required_trades=100,
        patterns_mined=0,
        buffer_size=0,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=0,
        data_exhausted=False,
    )
    assert observed.stage_trades == 10
    assert stall.is_stalled is False

    plan = client.meta_decide(stage, snap, trigger="periodic")
    assert plan.rationale == "bus_no_response"
    assert client.meta_metrics_payload(stage) == {}
    assert client.meta_scorecard_fields(stage, plan) == {}
    assert client.detect_stall(stage, winrate_history=[0.3], reward_history=[0.1]).threshold == 0
    assert client.wall_evaluate_trigger(stage, stage_trades=10, required=100) is None
    assert client.adaptation_try_recovery(stage, trigger_type="stall") == {"applied": False}
    assert client.adaptation_never_stop(stage, failure_key="x") == {"applied": False}
    assert client.adaptation_recovery_metrics(stage) == {}
    decision = client.autonomy_evaluate_terminal_stall(
        stage,
        pending={"terminal_stall_reason": "x"},
        stage_trades=1,
        required=2,
        constitution_violations=0,
        fitness_signal=0.1,
    )
    assert decision.needs_attention is True
    assert client.phoenix_begin_cycle(stage, stall_reason="x") is None
    assert client.plateau_detect_over_trading_trap(stage) is False
    assert client.plateau_check_enter(stage) is False
    assert client.plateau_should_trigger_evolution(stage) is False
    assert client.plateau_begin_evolution_step(stage) is None
    assert client.remediation_should_run(stage) is False
    assert client.remediation_can_start(stage) is False
    assert client.remediation_is_exhausted(stage) is False
    assert client.remediation_begin_step(stage) is None
    assert client.remediation_should_advance(stage) is False


@pytest.mark.unit
def test_birth_bus_client_emit_returns_correlation_id() -> None:
    client = BirthBusClient(EventBus(), BirthCurriculumConfig(), BirthRewardConfig())
    cid = client.emit("meta_metrics_payload", CurriculumStage.STAGE1_TREND, {})
    assert isinstance(cid, str)
    assert len(cid) > 0
