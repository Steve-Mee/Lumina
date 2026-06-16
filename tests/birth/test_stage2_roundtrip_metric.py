"""Stage 2 position-flat / round-trip metric tests (BRO v2 PR-T1)."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass


@pytest.mark.unit
def test_stage2_hold_dominant_fails_with_sufficient_range_ticks() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=150,
        hold_signals=900,
        total_signals=1000,
        range_hold_signals=450,
        range_total_signals=500,
        range_flat_bars=20,
        range_round_trips=1,
        constitution_violations=0,
        target_trades=3000,
        cfg=cfg,
    )
    assert result.passed is False
    assert "range_flat" in result.message


@pytest.mark.unit
def test_stage2_flat_and_roundtrip_sufficient_passes() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=150,
        hold_signals=500,
        total_signals=1000,
        range_hold_signals=100,
        range_total_signals=500,
        range_flat_bars=250,
        range_round_trips=30,
        constitution_violations=0,
        target_trades=3000,
        cfg=cfg,
    )
    assert result.passed is True
    assert "range_flat" in result.message
    assert result.range_round_trips == 30


@pytest.mark.unit
def test_stage2_falls_back_to_hold_ratio_when_few_range_ticks() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE2_RANGE,
        trades=300,
        wins=150,
        hold_signals=400,
        total_signals=1000,
        range_hold_signals=10,
        range_total_signals=20,
        range_flat_bars=0,
        range_round_trips=0,
        constitution_violations=0,
        target_trades=3000,
        cfg=cfg,
    )
    assert result.passed is True
    assert "hold_ratio" in result.message
