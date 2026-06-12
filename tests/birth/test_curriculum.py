from __future__ import annotations

import pytest

from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass, filter_ticks_for_stage


@pytest.mark.unit
def test_filter_ticks_for_trend_stage() -> None:
    ticks = [
        {"regime": "TREND_UP", "last": 1.0},
        {"regime": "NEUTRAL", "last": 2.0},
        {"regime": "TREND_DOWN", "last": 3.0},
    ]
    filtered = filter_ticks_for_stage(CurriculumStage.STAGE1_TREND, ticks)
    assert len(filtered) == 2


@pytest.mark.unit
def test_stage3_fails_on_constitution_violations() -> None:
    result = evaluate_stage_pass(
        CurriculumStage.STAGE3_MIXED,
        trades=200,
        wins=90,
        hold_signals=50,
        total_signals=200,
        constitution_violations=1,
        target_trades=5000,
    )
    assert result.passed is False
