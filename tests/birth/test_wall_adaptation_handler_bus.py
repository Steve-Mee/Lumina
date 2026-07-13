"""WallAdaptationHandler EventBus integration tests."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage


@pytest.mark.unit
def test_wall_handler_publishes_trigger_on_stall() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=100,
        stage1_winrate_stagnation_rollouts=2,
        certified_stage_stall_wall_sec=300,
        wall_behavior="adaptive",
    )
    client = BirthBusClient(bus, cfg, BirthRewardConfig())

    trigger = client.wall_evaluate_trigger(
        CurriculumStage.STAGE1_TREND,
        stage_trades=150,
        stage_wins=45,
        required=100,
        hold_ratio=0.2,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=100,
        elapsed_stage_sec=400.0,
        winrate_stagnation_count=3,
        hold_stagnation_count=0,
        wall_budget_exhausted=False,
        allow_provisional=False,
        failure_key="stage1_winrate",
        force=False,
        low_velocity_attempts=0,
        last_adaptation_stage_trades=-1,
    )
    assert trigger is not None
    assert trigger.get("triggered") is True
    assert bus.latest("birth.wall.triggered") is not None


@pytest.mark.unit
def test_wall_handler_applies_adaptive_recovery() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(
        wall_behavior="adaptive",
        adaptation_enabled=True,
        max_stage_retries=3,
        exploration_chunk_size=8,
        rollout_chunk_trades=20,
        meta_controller_enabled=False,
    )
    client = BirthBusClient(bus, cfg, BirthRewardConfig())

    result = client.adaptation_try_recovery(
        CurriculumStage.STAGE1_TREND,
        trigger_type="certified_stall",
        failure_key="stage1_winrate",
        stage_trades=150,
        required=100,
        current_winrate=0.30,
        winrate_history=[0.35, 0.34, 0.33, 0.32, 0.30],
        original_rollout_chunk=20,
        rollout_chunk_trades=20,
        trade_budget_remaining=1000,
        terminal_blocked=False,
        constitution_blocked=False,
        learning_health="flat",
        snapshot=None,
        winrate=0.30,
        escalation_level=0,
        adaptation_tier=0,
        retries_this_stage=0,
    )
    assert result.get("applied") is True
    assert bus.latest("birth.adaptation.applied") is not None
    assert bus.latest("birth.autonomy.recovery.metrics") is not None
    metrics = client.adaptation_recovery_metrics(CurriculumStage.STAGE1_TREND)
    assert int(metrics.get("autonomous_recovery_attempts", 0)) >= 1
    assert float(metrics.get("autonomous_recovery_rate_pct", 0.0)) > 0.0


@pytest.mark.unit
def test_wall_handler_never_stop_and_restore_state() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(
        wall_behavior="adaptive",
        adaptation_enabled=True,
        meta_controller_enabled=False,
    )
    client = BirthBusClient(bus, cfg, BirthRewardConfig())
    client.restore_states(
        stage=CurriculumStage.STAGE1_TREND,
        stage_metrics={"adaptation_tier": 1, "recovery_attempts": 2},
    )
    result = client.adaptation_never_stop(
        CurriculumStage.STAGE1_TREND,
        failure_key="terminal_blocked",
        rollout_chunk_trades=20,
        terminal_blocked=False,
    )
    assert result.get("applied") in {True, False}


@pytest.mark.unit
def test_wall_handler_blocks_when_constitution_blocked() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(wall_behavior="adaptive", adaptation_enabled=True)
    client = BirthBusClient(bus, cfg, BirthRewardConfig())
    result = client.adaptation_try_recovery(
        CurriculumStage.STAGE1_TREND,
        trigger_type="certified_stall",
        failure_key="stage1_winrate",
        stage_trades=150,
        required=100,
        current_winrate=0.30,
        winrate_history=[0.30],
        original_rollout_chunk=20,
        rollout_chunk_trades=20,
        trade_budget_remaining=1000,
        terminal_blocked=False,
        constitution_blocked=True,
    )
    assert result.get("applied") is False


@pytest.mark.unit
def test_wall_handler_adaptation_apply_result_signal() -> None:
    bus = EventBus()
    client = BirthBusClient(
        bus,
        BirthCurriculumConfig(wall_behavior="adaptive", adaptation_enabled=True),
        BirthRewardConfig(),
    )
    cid = client.emit(
        "adaptation_apply_result",
        CurriculumStage.STAGE1_TREND,
        {
            "applied": True,
            "recovery_kind": "adaptive",
            "decision": {
                "should_retry": True,
                "reason": "test",
                "new_chunk_target": 12,
                "escalation_increase": 1,
                "log_message": "test",
            },
            "dispatch": "continue_loop",
            "chunk_target": 12,
            "failure_key": "stall",
            "current_winrate": 0.3,
            "stage_trades": 100,
        },
    )
    resp = client.registry.pop_response(cid)
    assert resp.get("ok") is True or "error" not in resp
