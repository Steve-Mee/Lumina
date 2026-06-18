"""Unit tests for compute_stage_blocker SSOT (aligned with engine stall logic)."""

from __future__ import annotations

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_scorecard import compute_stage_blocker


@pytest.mark.unit
def test_stage1_blocker_winrate_below_target() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE1_TREND,
        stage_trades=200,
        stage_wins=26,
        hold_ratio=0.92,
        required=200,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
    )
    assert metric == "winrate"
    assert value is not None and value < 0.45
    assert reason is not None and "45%" in reason


@pytest.mark.unit
def test_stage1_no_blocker_below_trade_target() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE1_TREND,
        stage_trades=50,
        stage_wins=5,
        hold_ratio=0.90,
        required=200,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
    )
    assert metric is None
    assert value is None
    assert reason is None


@pytest.mark.unit
def test_stage2_blocker_flat_outside_band() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE2_RANGE,
        stage_trades=100,
        stage_wins=50,
        hold_ratio=0.90,
        required=100,
        constitution_violations=0,
        range_flat_ratio=0.15,
        range_round_trips=12,
        range_total_signals=200,
    )
    assert metric == "position_flat"
    assert value is not None
    assert reason is not None and "30" in reason


@pytest.mark.unit
def test_stage2_blocker_insufficient_round_trips() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE2_RANGE,
        stage_trades=100,
        stage_wins=50,
        hold_ratio=0.50,
        required=100,
        constitution_violations=0,
        range_flat_ratio=0.50,
        range_round_trips=2,
        range_total_signals=200,
    )
    assert metric == "round_trips"
    assert value == 2.0
    assert reason is not None and "round_trips" in reason


@pytest.mark.unit
def test_stage3_blocker_constitution_violations() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE3_MIXED,
        stage_trades=150,
        stage_wins=80,
        hold_ratio=0.40,
        required=150,
        constitution_violations=2,
        range_flat_ratio=0.50,
        range_round_trips=10,
        range_total_signals=100,
    )
    assert metric == "constitution_violations"
    assert value == 2.0
    assert reason is not None and "violations" in reason
