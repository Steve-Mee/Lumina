"""Exhaustive BirthBusClient method coverage for facade lines."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.birth_bus_serde import serialize_learning_snapshot
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage


def _client() -> BirthBusClient:
    return BirthBusClient(
        EventBus(),
        BirthCurriculumConfig(
            meta_controller_enabled=True,
            stall_remediation_enabled=True,
            plateau_detection_enabled=True,
            phoenix_loop_enabled=True,
            adaptation_enabled=True,
            wall_behavior="adaptive",
            autonomous_recovery_enabled=True,
        ),
        BirthRewardConfig(),
    )


def _observe(client: BirthBusClient, stage: CurriculumStage = CurriculumStage.STAGE1_TREND):
    return client.meta_observe(
        stage,
        winrate_history=[0.3, 0.29, 0.28],
        reward_history=[0.1, 0.09, 0.08],
        stage_trades=200,
        required_trades=500,
        patterns_mined=2,
        buffer_size=128,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=1,
        data_exhausted=False,
        range_flat_ratio=0.1,
        range_round_trips=5,
    )


@pytest.mark.unit
def test_birth_bus_client_meta_decision_surface() -> None:
    client = _client()
    stage = CurriculumStage.STAGE1_TREND
    snap, _ = _observe(client, stage)
    plan = client.meta_decide(stage, snap, trigger="periodic")
    client.meta_decide_pre_rollout(stage, snap, base_explore_steps=8)
    client.meta_decide_after_rollout(stage, snap)
    client.meta_decide_committed_rollout(stage, snap)
    client.meta_on_probe_complete(stage, snap, probe_winrate=0.35, probe_trades=10)
    client.meta_maybe_start_self_eval(stage, snap, strong_recovery_attempts=0, attempt=0)
    client.meta_evaluate_provisional_fallback(stage, snap, constitution_violations=0)
    client.meta_apply_explore_multiplier(stage, explore_steps=12)
    client.meta_format_self_eval_suffix(stage)
    client.meta_scorecard_fields(stage, plan)
    assert client.meta_controller is not None


@pytest.mark.unit
def test_birth_bus_client_plateau_surface() -> None:
    client = _client()
    stage = CurriculumStage.STAGE2_RANGE
    snap, _ = _observe(client, stage)
    client.plateau_check_enter(
        stage,
        stage_trades=400,
        stage_wins=120,
        required=200,
        winrate_trend_slope=0.0,
        velocity_stall_attempts=0,
        meta_self_eval_phase="idle",
        pass_metric_target=0.4,
        plateau_quarantine_active=False,
    )
    client.plateau_enter(stage, snapshot=serialize_learning_snapshot(snap))
    client.plateau_should_trigger_evolution(stage, stage_trades=400, required=200)
    client.plateau_begin_evolution_step(stage, stage_trades=400, required=200)
    client.plateau_record_outcome(stage, winrate=0.32, trades=20)
    assert client.plateau_state is not None


@pytest.mark.unit
def test_birth_bus_client_remediation_surface() -> None:
    client = _client()
    stage = CurriculumStage.STAGE1_TREND
    client.remediation_should_run(stage, stall_reason="plateau_evolution_exhausted")
    if client.remediation_can_start(stage):
        client.remediation_begin_cycle(stage, winrate_at_start=0.35, max_cycles=3, cycle=1)
        client.remediation_begin_step(stage, cycle=1, step=1, max_steps=5)
        client.remediation_should_advance(stage, cycle=1, step=1, winrate=0.36)
        client.remediation_increment_rollout(stage)
        client.remediation_record_outcome(stage, winrate=0.37, trades=10)
        client.remediation_patch_state(stage, cycles_completed=1)
    assert client.remediation_state is not None


@pytest.mark.unit
def test_birth_bus_client_property_accessors() -> None:
    client = _client()
    _ = client.autonomy_state
    _ = client.phoenix_state
    _ = client.wall_adaptation_state
    client.autonomy_evaluate_terminal_stall(
        CurriculumStage.STAGE1_TREND,
        pending={"terminal_stall_reason": "stage_stalled"},
        stage_trades=100,
        required=500,
        constitution_violations=0,
        fitness_signal=0.3,
        recommended_recovery_action="expand_data",
    )
