"""Fail-closed Stage-2 expectancy quality ownership (live thrash fix)."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.expectancy_stall import (
    coerce_meta_plan_under_expectancy_quality,
    plan_is_expectancy_thrash,
    snapshot_expectancy_stall,
)
from lumina_core.birth.meta_controller import BirthMetaController
from lumina_core.birth.meta_controller_types import (
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
)


def _live_like_snap(**overrides: object) -> LearningSnapshot:
    base = dict(
        winrate_history=(0.24, 0.27, 0.288, 0.27, 0.276),
        reward_history=(-1500.0,) * 5,
        stage_trades=550,
        required_trades=300,
        patterns_mined=20000,
        patterns_last_inject=2000,
        oracle_wins_last_inject=2000,
        buffer_size=5000,
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
        combined_velocity=-50.0,
        is_stalled=True,
        pattern_quality=1.0,
        learning_health=LearningHealth.DECLINING,
        volume_gate_passed=True,
        range_flat_ratio=0.47,
        range_round_trips=550,
        constitution_violations=0,
        range_total_signals=2500,
        plateau_active=False,
        expectancy_quality_step=1,
        stage_wins=149,
        rolling_winrate=0.27,
    )
    base.update(overrides)
    return LearningSnapshot(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_periodic_never_declining_thrash_when_stall() -> None:
    cfg = BirthCurriculumConfig(meta_controller_enabled=True, stage2_expectancy_floor=-0.15)
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    plan = meta.decide_periodic_review(_live_like_snap())
    assert plan.primary != RecoveryStrategy.EXPLORE_BOOST
    assert "periodic_declining_pattern_focus_explore" not in plan.rationale
    assert "stage2_expectancy" in plan.rationale or "stage2_" in plan.rationale
    assert RecoveryStrategy.EXPLORE_BOOST not in plan.secondary


@pytest.mark.unit
def test_after_rollout_quality_not_explore_boost() -> None:
    cfg = BirthCurriculumConfig(meta_controller_enabled=True, stage2_expectancy_floor=-0.15)
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    plan = meta.decide_after_rollout(_live_like_snap())
    assert plan.primary != RecoveryStrategy.EXPLORE_BOOST
    assert "stage2_expectancy" in plan.rationale or "stage2_stall" in plan.rationale


@pytest.mark.unit
def test_after_rollout_stage3_overtrade_not_explore_boost() -> None:
    """12/08 Stage-3: WR 25.6% + flat 2.3% must not after_rollout explore_boost."""
    cfg = BirthCurriculumConfig(
        meta_controller_enabled=True,
        stage2_expectancy_floor=-0.15,
        stage3_winrate_floor=0.35,
        stage3_position_flat_min=0.25,
    )
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    snap = _live_like_snap(
        stage=CurriculumStage.STAGE3_MIXED,
        stage_trades=636,
        required_trades=500,
        stage_wins=163,
        rolling_winrate=0.256,
        range_flat_ratio=0.023,
        range_total_signals=5000,
        is_stalled=True,
        volume_gate_passed=True,
        learning_health=LearningHealth.DECLINING,
    )
    plan = meta.decide_after_rollout(snap)
    assert plan.primary != RecoveryStrategy.EXPLORE_BOOST
    assert RecoveryStrategy.EXPLORE_BOOST not in plan.secondary


@pytest.mark.unit
def test_periodic_stage3_declining_not_explore_boost() -> None:
    cfg = BirthCurriculumConfig(
        meta_controller_enabled=True,
        stage2_expectancy_floor=-0.15,
        stage3_winrate_floor=0.35,
    )
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    snap = _live_like_snap(
        stage=CurriculumStage.STAGE3_MIXED,
        stage_trades=636,
        required_trades=500,
        stage_wins=163,
        rolling_winrate=0.256,
        range_flat_ratio=0.32,
        range_total_signals=5000,
        volume_gate_passed=True,
        learning_health=LearningHealth.DECLINING,
        is_stalled=True,
    )
    plan = meta.decide_periodic_review(snap)
    assert plan.primary != RecoveryStrategy.EXPLORE_BOOST
    assert "periodic_declining_pattern_focus_explore" not in plan.rationale
    assert RecoveryStrategy.EXPLORE_BOOST not in plan.secondary


@pytest.mark.unit
def test_coerce_rewrites_explore_boost_under_stall() -> None:
    snap = _live_like_snap()
    cfg = BirthCurriculumConfig(stage2_expectancy_floor=-0.15)
    thrash = MetaActionPlan(
        primary=RecoveryStrategy.EXPLORE_BOOST,
        secondary=(RecoveryStrategy.PATTERN_INJECT,),
        rationale="periodic_declining_pattern_focus_explore",
        snapshot=snap,
    )
    assert plan_is_expectancy_thrash(thrash)
    fixed = coerce_meta_plan_under_expectancy_quality(
        thrash, snap=snap, cfg=cfg, exploration_steps=2000
    )
    assert fixed.primary != RecoveryStrategy.EXPLORE_BOOST
    assert "stage2_expectancy" in fixed.rationale
    assert RecoveryStrategy.EXPLORE_BOOST not in fixed.secondary


@pytest.mark.unit
def test_exception_path_failclosed_not_declining_thrash() -> None:
    """Even if quality builder is stressed, periodic must not thrash with explore_boost."""
    cfg = BirthCurriculumConfig(meta_controller_enabled=True, stage2_expectancy_floor=-0.15)
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    # Valid stall snap — quality path must win.
    plan = meta.decide_periodic_review(_live_like_snap(stage_wins=100, rolling_winrate=0.20))
    assert plan.primary != RecoveryStrategy.EXPLORE_BOOST
    assert "periodic_declining_pattern_focus_explore" != plan.rationale


@pytest.mark.unit
def test_hold_trap_coerce_not_explore_boost_under_stall() -> None:
    snap = _live_like_snap()
    cfg = BirthCurriculumConfig(stage2_expectancy_floor=-0.15)
    thrash = MetaActionPlan(
        primary=RecoveryStrategy.EXPLORE_BOOST,
        explore_steps=8000,
        rationale="hold_trap_forced_explore",
        snapshot=snap,
    )
    assert plan_is_expectancy_thrash(thrash)
    fixed = coerce_meta_plan_under_expectancy_quality(
        thrash, snap=snap, cfg=cfg, exploration_steps=2000
    )
    assert fixed.primary != RecoveryStrategy.EXPLORE_BOOST
    assert int(fixed.explore_steps) < 8000


@pytest.mark.unit
def test_stage3_overtrade_quality_owns_no_explore_boost() -> None:
    """12/08 session 1 Stage-3: WR 25.6% + flat 2.3% → quality owns."""
    snap = _live_like_snap(
        stage=CurriculumStage.STAGE3_MIXED,
        stage_trades=636,
        required_trades=500,
        stage_wins=163,
        rolling_winrate=0.256,
        range_flat_ratio=0.023,
        range_total_signals=5000,
        range_round_trips=636,
        winrate_history=(0.26, 0.25, 0.256),
    )
    cfg = BirthCurriculumConfig(
        stage2_expectancy_floor=-0.15,
        stage3_winrate_floor=0.35,
        stage3_position_flat_min=0.25,
    )
    assert snapshot_expectancy_stall(snap, cfg=cfg) is True
    thrash = MetaActionPlan(
        primary=RecoveryStrategy.EXPLORE_BOOST,
        explore_steps=8000,
        rationale="stage3_wr_recovery_explore",
        snapshot=snap,
    )
    fixed = coerce_meta_plan_under_expectancy_quality(
        thrash, snap=snap, cfg=cfg, exploration_steps=2000
    )
    assert fixed.primary != RecoveryStrategy.EXPLORE_BOOST


@pytest.mark.unit
def test_scorecard_never_surfaces_explore_boost_under_stall() -> None:
    cfg = BirthCurriculumConfig(meta_controller_enabled=True, stage2_expectancy_floor=-0.15)
    meta = BirthMetaController(cfg=cfg, baseline_reward=BirthRewardConfig())
    snap = _live_like_snap()
    thrash = MetaActionPlan(
        primary=RecoveryStrategy.EXPLORE_BOOST,
        rationale="periodic_declining_pattern_focus_explore",
        snapshot=snap,
    )
    fields = meta.scorecard_fields(thrash)
    assert fields["meta_primary_strategy"] != "explore_boost"
