"""Stage-4 mean-R capture controller — no slack loophole."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.foundation_metrics import S4_MEAN_R_SLACK, mean_loss_r, mean_win_r
from lumina_core.birth.meta_controller import BirthMetaController, RecoveryStrategy
from lumina_core.birth.stage4_mean_r_meta import (
    stage4_mean_r_failing,
    stage4_mean_r_gap,
    stage4_mean_r_reward_tweak,
)


@pytest.mark.unit
def test_stage4_mean_r_failing_matches_live_gap() -> None:
    assert stage4_mean_r_failing(-0.7458, -0.3694) is True
    assert stage4_mean_r_gap(-0.7458, -0.3694) == pytest.approx(
        -0.3694 - S4_MEAN_R_SLACK - (-0.7458)
    )
    assert stage4_mean_r_failing(-0.40, -0.3694) is False
    assert S4_MEAN_R_SLACK == pytest.approx(0.10)


@pytest.mark.unit
def test_mean_win_loss_r_split() -> None:
    rs = [1.15, -1.0, 0.40, -1.23, -1.23]
    assert mean_win_r(rs) == pytest.approx((1.15 + 0.40) / 2)
    assert mean_loss_r(rs) == pytest.approx((-1.0 - 1.23 - 1.23) / 3)


@pytest.mark.unit
def test_stage4_pre_rollout_does_not_hold_on_mean_r_fail() -> None:
    ctrl = BirthMetaController(BirthCurriculumConfig(), BirthRewardConfig())
    snap, _ = ctrl.observe(
        winrate_history=[0.28, 0.29, 0.30, 0.30, 0.30, 0.30],
        reward_history=[0.01, 0.01, 0.02, 0.02, 0.02, 0.02],
        stage_trades=850,
        required_trades=100,
        patterns_mined=80,
        buffer_size=400,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=0,
        data_exhausted=False,
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        intra_hard_pct=None,
        volume_gate_passed=True,
        mean_r=-0.7458,
        e_mech=-0.3694,
        median_loss_r=1.23,
    )
    plan = ctrl.decide_pre_rollout(
        snap,
        base_explore_steps=512,
        wall_budget_exhausted=False,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
    )
    assert plan.primary == RecoveryStrategy.REWARD_SHAPING_TWEAK
    assert RecoveryStrategy.HOLD not in plan.secondary
    assert plan.rationale == "stage4_mean_r_capture"
    assert plan.reward_tweak is not None
    assert plan.reward_tweak.expectancy_coeff >= 0.5
    assert plan.reward_tweak.quality_win_bonus_coeff >= 0.25


@pytest.mark.unit
def test_stage4_pre_rollout_hold_when_mean_r_clears_slack() -> None:
    ctrl = BirthMetaController(BirthCurriculumConfig(), BirthRewardConfig())
    snap, _ = ctrl.observe(
        winrate_history=[0.32, 0.33, 0.34, 0.35, 0.36, 0.37],
        reward_history=[0.02, 0.03, 0.04, 0.05, 0.06, 0.07],
        stage_trades=200,
        required_trades=100,
        patterns_mined=80,
        buffer_size=400,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=0,
        data_exhausted=False,
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        intra_hard_pct=None,
        volume_gate_passed=True,
        mean_r=-0.40,
        e_mech=-0.3694,
        median_loss_r=1.1,
    )
    plan = ctrl.decide_pre_rollout(
        snap,
        base_explore_steps=512,
        wall_budget_exhausted=False,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
    )
    assert plan.rationale != "stage4_mean_r_capture"
    assert plan.primary == RecoveryStrategy.HOLD


@pytest.mark.unit
def test_stage4_periodic_mean_r_not_occupancy_taxi_when_exam_armed() -> None:
    ctrl = BirthMetaController(BirthCurriculumConfig(), BirthRewardConfig())
    snap, _ = ctrl.observe(
        winrate_history=[0.32, 0.31, 0.30, 0.29, 0.28, 0.27],
        reward_history=[0.02, 0.01, 0.0, -0.01, -0.02, -0.03],
        stage_trades=792,
        required_trades=100,
        patterns_mined=80,
        buffer_size=400,
        escalation_level=5,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=2,
        data_exhausted=False,
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        intra_hard_pct=None,
        volume_gate_passed=True,
        mean_r=-0.817,
        e_mech=-0.342,
        median_loss_r=1.20,
        range_flat_ratio=0.2499,
        range_total_signals=54706,
        occupancy_exam_armed=True,
    )
    plan = ctrl.decide_review(snap, trigger="periodic")
    assert plan.rationale == "stage4_mean_r_capture"
    assert "occupancy_taxi" not in str(plan.rationale)


@pytest.mark.unit
def test_stage4_periodic_does_not_pattern_inject_on_mean_r_fail() -> None:
    ctrl = BirthMetaController(BirthCurriculumConfig(), BirthRewardConfig())
    snap, _ = ctrl.observe(
        winrate_history=[0.32, 0.31, 0.30, 0.29, 0.28, 0.27],
        reward_history=[0.02, 0.01, 0.0, -0.01, -0.02, -0.03],
        stage_trades=810,
        required_trades=100,
        patterns_mined=80,
        buffer_size=400,
        escalation_level=5,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=2,
        data_exhausted=False,
        stage=CurriculumStage.STAGE4_VIABLE_PLANT,
        intra_hard_pct=None,
        volume_gate_passed=True,
        mean_r=-0.7089,
        e_mech=-0.3449,
        median_loss_r=1.21,
        range_flat_ratio=0.2694,
        range_total_signals=53222,
        occupancy_exam_armed=True,
    )
    plan = ctrl.decide_review(snap, trigger="periodic")
    assert plan.rationale == "stage4_mean_r_capture"
    assert plan.primary == RecoveryStrategy.REWARD_SHAPING_TWEAK
    assert RecoveryStrategy.PATTERN_INJECT not in plan.secondary


@pytest.mark.unit
def test_reward_tweak_never_lowers_coeffs() -> None:
    active = BirthRewardConfig(expectancy_coeff=0.7, quality_win_bonus_coeff=0.4)
    out = stage4_mean_r_reward_tweak(active, step=0.05, cap=0.65)
    assert out.expectancy_coeff == pytest.approx(0.7)
    assert out.quality_win_bonus_coeff == pytest.approx(0.45)
