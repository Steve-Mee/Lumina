from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.starship_birth import (
    compute_expectancy_proxy,
    evaluate_stage1_edgescore,
)


@pytest.mark.unit
def test_expectancy_uses_max_of_lifetime_and_rolling() -> None:
    # Lifetime 32%, rolling 40% -> effective 40% -> expectancy -0.10
    lifetime_only = compute_expectancy_proxy(wins=80, trades=250)
    with_roll = compute_expectancy_proxy(wins=80, trades=250, rolling_winrate=0.40)
    assert lifetime_only == pytest.approx(-0.18)
    assert with_roll == pytest.approx(-0.10)


@pytest.mark.unit
def test_rolling_hygiene_no_longer_fights_expectancy() -> None:
    cfg = BirthCurriculumConfig(
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        stage1_expectancy_floor=-0.15,
        stage1_entropy_floor=0.05,
        starship_entropy_required_after_ppo_steps=500,
    )
    # Lifetime WR 32% fails alone; rolling 40% clears hygiene AND expectancy.
    edge = evaluate_stage1_edgescore(
        trades=250,
        wins=80,
        hold_signals=500,
        total_signals=1000,
        constitution_violations=0,
        required=200,
        cfg=cfg,
        rolling_winrate=0.40,
        entropy=0.20,
        ppo_steps=5000,
    )
    assert edge.hygiene_ok is True
    assert edge.expectancy_ok is True
    assert edge.entropy_ok is True
    assert edge.passed is True
