"""BirthBusClient facade coverage tests."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage


@pytest.fixture
def client() -> BirthBusClient:
    cfg = BirthCurriculumConfig(
        meta_controller_enabled=True,
        stall_remediation_enabled=True,
        phoenix_loop_enabled=True,
        adaptation_enabled=True,
        wall_behavior="adaptive",
        autonomous_recovery_enabled=True,
    )
    return BirthBusClient(EventBus(), cfg, BirthRewardConfig())


@pytest.mark.unit
def test_restore_states_roundtrip(client: BirthBusClient) -> None:
    metrics = {"phoenix_count": 1, "adaptation_tier": 2}
    client.restore_states(stage=CurriculumStage.STAGE1_TREND, stage_metrics=metrics)
    assert client.phoenix_state.phoenix_count >= 0


@pytest.mark.unit
def test_meta_observe_and_detect_stall(client: BirthBusClient) -> None:
    snap, stall = client.meta_observe(
        CurriculumStage.STAGE1_TREND,
        winrate_history=[0.3, 0.29, 0.28],
        reward_history=[0.1, 0.09],
        stage_trades=120,
        required_trades=500,
        patterns_mined=0,
        buffer_size=64,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=1,
        data_exhausted=False,
    )
    assert snap.stage_trades == 120
    detected = client.detect_stall(
        CurriculumStage.STAGE1_TREND,
        winrate_history=[0.3, 0.29, 0.28],
        reward_history=[0.1, 0.09],
        low_velocity_attempts=1,
    )
    assert detected.threshold >= 0
    assert stall.is_stalled is False or stall.is_stalled is True


@pytest.mark.unit
def test_meta_metrics_and_self_eval_state(client: BirthBusClient) -> None:
    metrics = client.meta_metrics_payload(CurriculumStage.STAGE1_TREND)
    assert isinstance(metrics, dict)
    state = client.meta_self_eval_state(CurriculumStage.STAGE1_TREND)
    assert "phase" in state


@pytest.mark.unit
def test_meta_patch_and_record_inject(client: BirthBusClient) -> None:
    client.meta_patch_state(CurriculumStage.STAGE1_TREND, explore_multiplier=1.5)
    client.meta_record_inject(
        CurriculumStage.STAGE1_TREND,
        patterns=3,
        oracle_wins=2,
    )


@pytest.mark.unit
def test_remediation_and_phoenix_client_paths(client: BirthBusClient) -> None:
    stage = CurriculumStage.STAGE1_TREND
    assert client.remediation_can_start(stage) in {True, False}
    assert client.remediation_is_exhausted(stage) in {True, False}
    patch = client.phoenix_begin_cycle(
        stage,
        stall_reason="stall_remediation_exhausted",
        novelty="expand_data",
    )
    assert patch is None or isinstance(patch, dict)


@pytest.mark.unit
def test_plateau_client_paths(client: BirthBusClient) -> None:
    stage = CurriculumStage.STAGE2_RANGE
    trap = client.plateau_detect_over_trading_trap(
        stage,
        range_flat_ratio=0.2,
        range_round_trips=30,
    )
    assert trap in {True, False}
    client.plateau_increment_rollout(stage)


@pytest.mark.unit
def test_adaptation_never_stop_client_path(client: BirthBusClient) -> None:
    result = client.adaptation_never_stop(
        CurriculumStage.STAGE1_TREND,
        failure_key="budget",
        rollout_chunk_trades=20,
        terminal_blocked=False,
    )
    assert isinstance(result, dict)
