"""Pilot-2 skill metric: plant FORCE_OPEN ≠ pilot grade."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.stage2_skill_metric import (
    resolve_stage2_skill_counts,
    skill_expectancy_for_pass,
)
from lumina_core.birth.starship_edgescore_stage2 import evaluate_stage2_edgescore
from tests.birth.honest_settlement import honest_closes


@pytest.mark.unit
def test_plant_trades_excluded_from_skill_expectancy() -> None:
    sc = resolve_stage2_skill_counts(
        total_trades=400,
        total_wins=100,  # 25% total
        policy_trades=200,
        policy_wins=80,  # 40% pilot
        plant_trades=200,
        plant_wins=20,  # 10% plant
        skill_only=True,
        required=300,
        skill_min_trades=150,
    )
    assert sc.skill_eligible is True
    assert sc.skill_winrate == pytest.approx(0.40)
    assert sc.skill_expectancy == pytest.approx(-0.10)
    assert sc.total_winrate == pytest.approx(0.25)
    exp, ok, *_ = skill_expectancy_for_pass(sc)
    assert ok is True
    assert exp == pytest.approx(-0.10)


@pytest.mark.unit
def test_thin_pilot_sample_not_eligible() -> None:
    sc = resolve_stage2_skill_counts(
        total_trades=400,
        total_wins=160,
        policy_trades=40,
        policy_wins=20,
        plant_trades=360,
        plant_wins=140,
        skill_only=True,
        required=300,
        skill_min_trades=150,
    )
    assert sc.skill_eligible is False
    _, ok, *_ = skill_expectancy_for_pass(sc)
    assert ok is False


@pytest.mark.unit
def test_edgescore_uses_skill_not_plant_inflation() -> None:
    """Plant can pad total WR down; skill pilot at 36% can pass expectancy leg."""
    cfg = BirthCurriculumConfig(
        stage2_edgescore_enabled=True,
        stage2_skill_metric_policy_only=True,
        stage2_skill_min_trades=100,
        stage2_expectancy_floor=-0.15,
    )
    # Total WR 25% fails; policy WR 36% → exp -0.14 >= -0.15
    edge = evaluate_stage2_edgescore(
        trades=400,
        wins=100,
        range_flat_ratio=0.45,
        range_round_trips=50,
        range_total_signals=500,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        ppo_steps=10_000,
        policy_trades=200,
        policy_wins=72,  # 36%
        plant_trades=200,
        plant_wins=28,
        consecutive_rolling_pass_windows=2,
        **honest_closes(400),
    )
    assert edge.expectancy_ok is True
    assert edge.activity_ok is True
    assert edge.passed is True


@pytest.mark.unit
def test_edgescore_fails_when_pilot_weak_even_if_volume_ok() -> None:
    cfg = BirthCurriculumConfig(
        stage2_edgescore_enabled=True,
        stage2_skill_metric_policy_only=True,
        stage2_skill_min_trades=100,
        stage2_expectancy_floor=-0.15,
    )
    edge = evaluate_stage2_edgescore(
        trades=400,
        wins=100,
        range_flat_ratio=0.45,
        range_round_trips=50,
        range_total_signals=500,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        ppo_steps=10_000,
        policy_trades=200,
        policy_wins=50,  # 25% → exp -0.25
        plant_trades=200,
        plant_wins=50,
    )
    assert edge.expectancy_ok is False
    assert edge.passed is False
