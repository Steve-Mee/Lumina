"""Meta periodic/after_rollout must own Stage-2 expectancy stall (no explore_boost thrash)."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.expectancy_stall import (
    build_expectancy_quality_meta_fields,
    snapshot_expectancy_stall,
)
from lumina_core.birth.meta_controller import BirthMetaController
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    RecoveryStrategy,
)


def _stall_snap(**overrides: object) -> LearningSnapshot:
    base = dict(
        winrate_history=(0.26, 0.255, 0.258),
        reward_history=(-100.0, -80.0, -90.0),
        stage_trades=500,
        required_trades=300,
        patterns_mined=1000,
        patterns_last_inject=500,
        oracle_wins_last_inject=400,
        buffer_size=500,
        escalation_level=2,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=5,
        data_exhausted=False,
        stage=CurriculumStage.STAGE2_RANGE,
        intra_hard_pct=0.25,
        attempt=10,
        winrate_velocity=-0.01,
        reward_velocity=-1.0,
        combined_velocity=-1.0,
        is_stalled=True,
        pattern_quality=1.0,
        learning_health=LearningHealth.DECLINING,
        volume_gate_passed=True,
        range_flat_ratio=0.45,
        range_round_trips=400,
        constitution_violations=0,
        range_total_signals=800,
        plateau_active=True,
        expectancy_quality_step=1,
        stage_wins=130,
        rolling_winrate=0.26,
    )
    base.update(overrides)
    return LearningSnapshot(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_snapshot_detects_expectancy_stall() -> None:
    cfg = BirthCurriculumConfig(stage2_expectancy_floor=-0.15)
    assert snapshot_expectancy_stall(_stall_snap(), cfg=cfg)


@pytest.mark.unit
def test_quality_meta_never_explore_boost() -> None:
    for step in range(0, 5):
        fields = build_expectancy_quality_meta_fields(
            range_flat_ratio=0.45,
            remediation_step=step,
            base_explore_steps=2000,
            exploration_steps=2000,
        )
        assert fields["primary"] != "explore_boost"


@pytest.mark.unit
def test_periodic_review_uses_expectancy_ladder() -> None:
    cfg = BirthCurriculumConfig(
        meta_controller_enabled=True,
        stage2_expectancy_floor=-0.15,
        exploration_steps=2000,
        strong_recovery_explore_fraction=0.35,
        meta_explore_decay_stall=0.5,
    )
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    plan = meta.decide_periodic_review(_stall_snap())
    assert plan.primary != RecoveryStrategy.EXPLORE_BOOST
    assert "expectancy" in str(plan.rationale).lower() or plan.primary in {
        RecoveryStrategy.EXPLORE_REDUCE,
        RecoveryStrategy.PATTERN_INJECT,
        RecoveryStrategy.REWARD_SHAPING_TWEAK,
    }


@pytest.mark.unit
def test_after_rollout_uses_expectancy_ladder() -> None:
    cfg = BirthCurriculumConfig(
        meta_controller_enabled=True,
        stage2_expectancy_floor=-0.15,
        exploration_steps=2000,
        strong_recovery_explore_fraction=0.35,
        meta_explore_decay_stall=0.5,
    )
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    plan = meta.decide_after_rollout(_stall_snap())
    assert plan.primary != RecoveryStrategy.EXPLORE_BOOST
    assert "expectancy" in str(plan.rationale).lower() or plan.primary in {
        RecoveryStrategy.EXPLORE_REDUCE,
        RecoveryStrategy.PATTERN_INJECT,
    }
