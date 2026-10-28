"""Pre-rollout: in-band expectancy stall owns over hold_stagnation explore_boost."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import BirthMetaController
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    RecoveryStrategy,
)


def _snap(**overrides: object) -> LearningSnapshot:
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
def test_pre_rollout_quality_beats_hold_stagnation() -> None:
    cfg = BirthCurriculumConfig(
        meta_controller_enabled=True,
        stage2_expectancy_floor=-0.15,
        exploration_steps=2000,
        stage2_hold_stagnation_rollouts=1,
        strong_recovery_explore_fraction=0.35,
    )
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    plan = meta.decide_pre_rollout(
        _snap(),
        base_explore_steps=2000,
        wall_budget_exhausted=False,
        winrate_stagnation_count=0,
        hold_stagnation_count=99,  # would have forced explore_boost pre-fix
        over_trading_trap=False,
    )
    assert plan.primary != RecoveryStrategy.EXPLORE_BOOST
    assert "expectancy" in str(plan.rationale).lower()
