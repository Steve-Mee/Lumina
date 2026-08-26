"""Stage-2 expectancy stall + quality ladder + swarm defer."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.expectancy_stall import (
    detect_expectancy_stall,
    recommended_expectancy_recovery_action,
    should_stage2_early_quality_hard_stop,
    stage2_expectancy_live,
    stage2_should_defer_swarm_for_expectancy,
)
from lumina_core.birth.starship_edgescore_stage2 import (
    evaluate_stage2_edgescore,
    stage2_expectancy_floor,
)
from lumina_core.birth.starship_edgescore_champion import humanize_edgescore_blocker
from lumina_core.birth.starship_edgescore_core import EdgeScoreResult
from tests.birth.honest_settlement import honest_closes


@pytest.mark.unit
def test_stage2_expectancy_floor_not_survival() -> None:
    cfg = BirthCurriculumConfig(
        birth_survival_pass_enabled=True,
        birth_survival_expectancy_floor=-0.50,
        stage2_expectancy_floor=-0.15,
    )
    assert stage2_expectancy_floor(cfg) == pytest.approx(-0.15)


@pytest.mark.unit
def test_stage2_edgescore_uses_rolling_wr_for_expectancy() -> None:
    cfg = BirthCurriculumConfig(
        stage2_expectancy_floor=-0.15,
        stage2_edgescore_enabled=True,
        stage2_pass_durable_enabled=True,
        stage2_pass_rolling_streak=2,
        stage2_pass_lifetime_delta=0.05,
    )
    # Lifetime 29% WR → exp -0.21 fails without rolling.
    edge_life = evaluate_stage2_edgescore(
        trades=1000,
        wins=290,
        range_flat_ratio=0.50,
        range_round_trips=50,
        range_total_signals=500,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        ppo_steps=5000,
        rolling_winrate=None,
    )
    assert edge_life.expectancy_ok is False
    # Rolling lift alone is not durable when life < 30% (plan A+C).
    edge_roll_weak_life = evaluate_stage2_edgescore(
        trades=1000,
        wins=290,  # 29% < 30% life band
        range_flat_ratio=0.50,
        range_round_trips=50,
        range_total_signals=500,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        ppo_steps=5000,
        rolling_winrate=0.40,
        consecutive_rolling_pass_windows=2,
    )
    assert edge_roll_weak_life.passed is False
    # Rolling 40% + life 31% + 2 windows → durable pass (exp from roll).
    edge_roll = evaluate_stage2_edgescore(
        trades=1000,
        wins=310,  # 31% ≥ 30%
        range_flat_ratio=0.50,
        range_round_trips=50,
        range_total_signals=500,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        ppo_steps=5000,
        rolling_winrate=0.40,
        consecutive_rolling_pass_windows=2,
        **honest_closes(1000),
    )
    assert edge_roll.expectancy_ok is False
    assert edge_roll.pass_expectancy_source == "rolling_hud_only"
    assert edge_roll.passed is False


@pytest.mark.unit
def test_humanize_stage2_expectancy_shows_quality_floor() -> None:
    cfg = BirthCurriculumConfig(
        birth_survival_pass_enabled=True,
        stage2_expectancy_floor=-0.15,
    )
    edge = EdgeScoreResult(
        passed=False,
        score=0.8,
        hygiene_ok=True,
        activity_ok=True,
        entropy_ok=True,
        expectancy_ok=False,
        constitution_ok=True,
        message="x",
    )
    text = humanize_edgescore_blocker(
        edge, cfg=cfg, wins=290, trades=1000, stage="stage2_range"
    )
    assert "-15%" in text or ">= -15%" in text
    assert "-50%" not in text
    assert "Range quality WR" in text or "35%" in text


@pytest.mark.unit
def test_detect_expectancy_stall_in_band_low_wr() -> None:
    cfg = BirthCurriculumConfig(stage2_expectancy_floor=-0.15)
    assert detect_expectancy_stall(
        stage_is_range=True,
        range_flat_ratio=0.50,
        range_total_signals=500,
        stage_trades=500,
        stage_wins=145,
        required=300,
        plateau_active=True,
        trades_beyond_gate=200,
        cfg=cfg,
    )


@pytest.mark.unit
def test_detect_expectancy_stall_not_when_flat_trap() -> None:
    cfg = BirthCurriculumConfig(stage2_expectancy_floor=-0.15)
    # Outside soft band → occupancy traps own the recovery path.
    assert not detect_expectancy_stall(
        stage_is_range=True,
        range_flat_ratio=0.95,
        range_total_signals=500,
        stage_trades=500,
        stage_wins=145,
        required=300,
        plateau_active=True,
        cfg=cfg,
    )


@pytest.mark.unit
def test_swarm_defer_while_quality_budget() -> None:
    cfg = BirthCurriculumConfig(
        stage2_expectancy_quality_max_steps=4,
        stage2_expectancy_swarm_defer_steps=2,
    )
    assert stage2_should_defer_swarm_for_expectancy(
        expectancy_stall=True,
        remediation_step=1,
        evolution_step=0,
        cfg=cfg,
    )
    assert not stage2_should_defer_swarm_for_expectancy(
        expectancy_stall=True,
        remediation_step=10,
        evolution_step=5,
        cfg=cfg,
    )


@pytest.mark.unit
def test_recovery_action_ladder_order() -> None:
    assert recommended_expectancy_recovery_action(range_flat_ratio=0.35, remediation_step=0) == (
        "policy_rollback"
    )
    assert recommended_expectancy_recovery_action(range_flat_ratio=0.35, remediation_step=1) == (
        "expectancy_quality_reward"
    )


@pytest.mark.unit
def test_stage2_expectancy_live_prefers_rolling() -> None:
    exp = stage2_expectancy_live(stage_trades=1000, stage_wins=200, rolling_winrate=0.40)
    assert exp == pytest.approx(-0.10)


@pytest.mark.unit
def test_stage2_early_quality_hard_stop_audit_shape() -> None:
    """H1: flat out of band + dead expectancy past gate → hard-stop long before 3× burn."""
    cfg = BirthCurriculumConfig(stage2_expectancy_floor=-0.15)
    # 1200 trades, gate 300, WR ~20%, flat 27.6% — matches 2026-08-08 forensic
    assert should_stage2_early_quality_hard_stop(
        stage_is_range=True,
        stage_trades=1200,
        required=300,
        range_flat_ratio=0.2764,
        stage_wins=244,  # ~20.3%
        range_total_signals=2000,
        cfg=cfg,
    )


@pytest.mark.unit
def test_stage2_early_quality_hard_stop_not_before_min_beyond() -> None:
    cfg = BirthCurriculumConfig(stage2_expectancy_floor=-0.15)
    assert not should_stage2_early_quality_hard_stop(
        stage_is_range=True,
        stage_trades=320,  # only 20 beyond
        required=300,
        range_flat_ratio=0.20,
        stage_wins=60,
        range_total_signals=500,
        cfg=cfg,
    )


@pytest.mark.unit
def test_stage2_early_quality_hard_stop_not_when_healthy() -> None:
    cfg = BirthCurriculumConfig(stage2_expectancy_floor=-0.15)
    assert not should_stage2_early_quality_hard_stop(
        stage_is_range=True,
        stage_trades=600,
        required=300,
        range_flat_ratio=0.50,
        stage_wins=240,  # 40% WR
        rolling_winrate=0.40,
        range_total_signals=800,
        cfg=cfg,
    )
