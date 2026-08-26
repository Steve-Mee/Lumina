"""Lock Stage-2/3 early-quality floors: 26% fails, ≥35% can pass (truthful)."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.curriculum_pass import evaluate_stage_pass
from lumina_core.birth.starship_edgescore_stage2 import evaluate_stage2_edgescore
from lumina_core.birth.starship_edgescore_stage3 import evaluate_stage3_edgescore
from tests.birth.honest_settlement import foundation_eval_kwargs, honest_closes


@pytest.mark.unit
def test_stage2_fails_at_26pct_passes_at_40pct() -> None:
    cfg = BirthCurriculumConfig(stage2_edgescore_enabled=True, stage2_expectancy_floor=-0.15)
    fail = evaluate_stage2_edgescore(
        trades=500,
        wins=130,  # 26%
        range_flat_ratio=0.50,
        range_round_trips=50,
        range_total_signals=800,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        rolling_winrate=0.26,
    )
    assert fail.passed is False
    assert fail.expectancy_ok is False

    ok = evaluate_stage2_edgescore(
        trades=500,
        wins=200,  # 40%
        range_flat_ratio=0.50,
        range_round_trips=50,
        range_total_signals=800,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        rolling_winrate=0.40,
        consecutive_rolling_pass_windows=2,
        **honest_closes(500),
    )
    assert ok.passed is True
    assert ok.expectancy_ok is True


@pytest.mark.unit
def test_stage2_never_uses_survival_floor() -> None:
    cfg = BirthCurriculumConfig(
        birth_survival_pass_enabled=True,
        birth_survival_expectancy_floor=-0.50,
        stage2_expectancy_floor=-0.15,
        stage2_edgescore_enabled=True,
    )
    # WR 30% → exp -0.20: would pass survival −0.50 but must fail Stage-2 quality.
    edge = evaluate_stage2_edgescore(
        trades=400,
        wins=120,
        range_flat_ratio=0.50,
        range_round_trips=40,
        range_total_signals=600,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        rolling_winrate=0.30,
    )
    assert edge.expectancy_ok is False
    assert edge.passed is False


@pytest.mark.unit
def test_stage3_early_quality_aligned_with_stage2() -> None:
    cfg = BirthCurriculumConfig(
        stage3_edgescore_enabled=True,
        stage2_expectancy_floor=-0.15,
        stage1_expectancy_floor=-0.15,
        stage3_winrate_floor=0.35,
    )
    fail = evaluate_stage3_edgescore(
        trades=500,
        wins=130,
        hold_signals=100,
        total_signals=500,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        rolling_winrate=0.26,
        hold_ratio=0.20,
    )
    assert fail.passed is False

    ok = evaluate_stage3_edgescore(
        trades=500,
        wins=200,
        hold_signals=100,
        total_signals=500,
        constitution_violations=0,
        required=300,
        cfg=cfg,
        entropy=0.2,
        rolling_winrate=0.40,
        hold_ratio=0.20,
        range_flat_ratio=0.40,
        range_total_signals=500,
        range_round_trips=50,
        **honest_closes(500),
    )
    assert ok.passed is True


@pytest.mark.unit
def test_evaluate_stage_pass_stage2_uses_edgescore() -> None:
    cfg = BirthCurriculumConfig(stage2_edgescore_enabled=True, stage2_expectancy_floor=-0.15)
    bad = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=400,
        wins=100,
        hold_signals=200,
        total_signals=500,
        range_hold_signals=200,
        range_total_signals=500,
        range_flat_bars=250,
        range_round_trips=40,
        constitution_violations=0,
        target_trades=3000,
        cfg=cfg,
        rolling_winrate=0.25,
        policy_entropy=0.2,
        ppo_steps=5000,
    )
    assert bad.passed is False

    good = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=400,
        wins=160,
        hold_signals=200,
        total_signals=500,
        range_hold_signals=200,
        range_total_signals=500,
        range_flat_bars=250,
        range_round_trips=40,
        constitution_violations=0,
        target_trades=3000,
        cfg=cfg,
        consecutive_rolling_pass_windows=2,
        **honest_closes(400),
        **foundation_eval_kwargs(policy_entropy=0.2, ppo_steps=5000),
    )
    assert good.passed is True
