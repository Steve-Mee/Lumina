"""Roundtrip tests for birth EventBus serde helpers."""

from __future__ import annotations

import pytest

from lumina_core.birth.birth_bus_serde import (
    deserialize_learning_snapshot,
    deserialize_meta_plan,
    serialize_learning_snapshot,
    serialize_meta_plan,
)
from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import (
    AdaptationDecision,
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
)


def _sample_snapshot() -> LearningSnapshot:
    return LearningSnapshot(
        winrate_history=(0.3, 0.31, 0.32),
        reward_history=(0.1, 0.12),
        stage_trades=150,
        required_trades=500,
        patterns_mined=3,
        patterns_last_inject=2,
        oracle_wins_last_inject=1,
        buffer_size=128,
        escalation_level=1,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=2,
        data_exhausted=False,
        stage=CurriculumStage.STAGE2_RANGE,
        intra_hard_pct=0.45,
        attempt=1,
        winrate_velocity=0.001,
        reward_velocity=0.002,
        combined_velocity=0.0015,
        is_stalled=True,
        pattern_quality=0.6,
        learning_health=LearningHealth.FLAT,
        volume_gate_passed=True,
        range_flat_ratio=0.12,
        range_round_trips=8,
        median_loss_r=1.12,
    )


@pytest.mark.unit
def test_learning_snapshot_roundtrip() -> None:
    original = _sample_snapshot()
    data = serialize_learning_snapshot(original)
    restored = deserialize_learning_snapshot(data)
    assert restored.stage == original.stage
    assert restored.winrate_history == original.winrate_history
    assert restored.reward_history == original.reward_history
    assert restored.stage_trades == original.stage_trades
    assert restored.learning_health == original.learning_health
    assert restored.range_round_trips == original.range_round_trips
    assert restored.median_loss_r == original.median_loss_r


@pytest.mark.unit
def test_learning_snapshot_defaults_on_empty_dict() -> None:
    snap = deserialize_learning_snapshot({})
    assert snap.stage == CurriculumStage.STAGE1_TREND
    assert snap.learning_health == LearningHealth.FLAT
    assert snap.stage_trades == 0


@pytest.mark.unit
def test_meta_plan_roundtrip_with_adaptation_and_snapshot() -> None:
    adapt = AdaptationDecision(
        should_retry=True,
        reason="stall_escalation",
        new_chunk_target=16,
        escalation_increase=1,
        log_message="forced",
    )
    reward = BirthRewardConfig()
    original = MetaActionPlan(
        primary=RecoveryStrategy.EXPLORE_BOOST,
        secondary=(RecoveryStrategy.PATTERN_INJECT,),
        explore_steps=12,
        explore_fraction=0.2,
        chunk_target=16,
        escalation_delta=1,
        mine=True,
        mine_aggressive=False,
        expand_data=True,
        reward_tweak=reward,
        intra_hard_pct_delta=0.05,
        enter_strong_recovery=False,
        exit_strong_recovery=False,
        adaptation=adapt,
        explore_steps_multiplier=1.5,
        trigger="adaptation",
        rationale="test rationale",
        suggest_provisional_pass=False,
        self_eval_phase="idle",
        committed_strategy="probe_a",
        snapshot=_sample_snapshot(),
    )
    data = serialize_meta_plan(original)
    restored = deserialize_meta_plan(data)
    assert restored.primary == original.primary
    assert restored.secondary == original.secondary
    assert restored.adaptation is not None
    assert restored.adaptation.reason == "stall_escalation"
    assert restored.snapshot is not None
    assert restored.snapshot.stage_trades == 150
    assert restored.trigger == "adaptation"


@pytest.mark.unit
def test_meta_plan_minimal_deserialize() -> None:
    plan = deserialize_meta_plan({"primary": RecoveryStrategy.HOLD.value})
    assert plan.primary == RecoveryStrategy.HOLD
    assert plan.adaptation is None
    assert plan.snapshot is None
