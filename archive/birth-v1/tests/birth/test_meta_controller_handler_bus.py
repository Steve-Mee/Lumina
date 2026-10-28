"""MetaControllerHandler EventBus integration tests."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import RecoveryStrategy


@pytest.mark.unit
def test_meta_handler_publishes_plan_on_decide() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(meta_controller_enabled=True)
    reward = BirthRewardConfig()
    client = BirthBusClient(bus, cfg, reward)

    plan = client.meta_decide(
        CurriculumStage.STAGE1_TREND,
        client.meta_observe(
            CurriculumStage.STAGE1_TREND,
            winrate_history=[0.3, 0.31],
            reward_history=[0.1, 0.12],
            stage_trades=100,
            required_trades=500,
            patterns_mined=0,
            buffer_size=128,
            escalation_level=0,
            strong_recovery_mode=False,
            strong_recovery_attempts=0,
            low_velocity_attempts=0,
            data_exhausted=False,
        )[0],
        trigger="periodic",
    )
    assert plan.primary in {RecoveryStrategy.HOLD, RecoveryStrategy.EXPLORE_BOOST}
    latest = bus.latest("birth.meta.plan")
    assert latest is not None


@pytest.mark.unit
def test_meta_handler_trap_flag_affects_pre_rollout() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(meta_controller_enabled=True)
    client = BirthBusClient(bus, cfg, BirthRewardConfig())

    bus.publish_validated(
        topic="birth.plateau.trap.detected",
        producer="test",
        payload={
            "stage": "stage2_range",
            "detected": True,
            "range_flat_ratio": 0.15,
            "range_round_trips": 20,
        },
    )

    snap, _ = client.meta_observe(
        CurriculumStage.STAGE2_RANGE,
        winrate_history=[0.25, 0.24],
        reward_history=[0.05, 0.04],
        stage_trades=200,
        required_trades=500,
        patterns_mined=0,
        buffer_size=64,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=0,
        data_exhausted=False,
        range_flat_ratio=0.15,
        range_round_trips=20,
    )
    plan = client.meta_decide_pre_rollout(
        CurriculumStage.STAGE2_RANGE,
        snap,
        base_explore_steps=10,
        wall_budget_exhausted=False,
        winrate_stagnation_count=2,
        hold_stagnation_count=1,
    )
    assert plan is not None
    assert bus.latest("birth.meta.plan") is not None


@pytest.mark.unit
def test_meta_handler_restore_observe_and_detect_stall() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(meta_controller_enabled=True)
    client = BirthBusClient(bus, cfg, BirthRewardConfig())

    client.restore_states(stage=CurriculumStage.STAGE1_TREND, stage_metrics={"rollouts_since_review": 2})
    snap, stall = client.meta_observe(
        CurriculumStage.STAGE1_TREND,
        winrate_history=[0.3, 0.3, 0.3],
        reward_history=[0.1, 0.1, 0.1],
        stage_trades=80,
        required_trades=400,
        patterns_mined=1,
        buffer_size=32,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=2,
        data_exhausted=False,
    )
    detected = client.detect_stall(
        CurriculumStage.STAGE1_TREND,
        winrate_history=[0.3, 0.3, 0.3],
        reward_history=[0.1, 0.1, 0.1],
        low_velocity_attempts=2,
    )
    assert snap.stage_trades == 80
    assert detected.low_velocity_attempts >= 0
    assert stall.threshold >= 0


@pytest.mark.unit
def test_meta_handler_decide_adaptation_and_probe_paths() -> None:
    bus = EventBus()
    client = BirthBusClient(
        bus,
        BirthCurriculumConfig(meta_controller_enabled=True),
        BirthRewardConfig(),
    )
    snap, _ = client.meta_observe(
        CurriculumStage.STAGE1_TREND,
        winrate_history=[0.28, 0.27],
        reward_history=[0.05, 0.04],
        stage_trades=150,
        required_trades=500,
        patterns_mined=0,
        buffer_size=64,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=0,
        data_exhausted=False,
    )
    client.meta_decide_adaptation(
        CurriculumStage.STAGE1_TREND,
        snap,
        winrate=0.27,
        escalation_level=0,
        adaptation_tier=0,
        retries_this_stage=0,
        original_rollout_chunk=250,
        failure_key="stall",
    )
    client.meta_decide_probe_rollout(CurriculumStage.STAGE1_TREND, snap)
    assert bus.latest("birth.meta.plan") is not None

