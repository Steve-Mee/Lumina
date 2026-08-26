"""Unit tests for compute_stage_blocker SSOT (aligned with engine stall logic)."""

from __future__ import annotations

import pytest

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_scorecard import compute_stage_blocker


@pytest.mark.unit
def test_stage1_blocker_missing_process_r_after_volume_gate() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE1_TREND,
        stage_trades=200,
        stage_wins=26,
        hold_ratio=0.92,
        required=150,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
    )
    assert metric == "median_loss_r"
    assert reason is not None and "median_loss_r" in reason


@pytest.mark.unit
def test_stage1_blocker_clears_when_foundation_physics_present() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE1_TREND,
        stage_trades=200,
        stage_wins=62,
        hold_ratio=0.33,
        required=150,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
        median_loss_r=1.1,
        geometry_net_rr=1.4,
        unique_calendar_days=40,
    )
    assert metric is None
    assert value is None
    assert reason is None


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
        stage_trades=250,
        stage_wins=80,
        hold_ratio=0.90,
        required=250,
        constitution_violations=0,
        range_flat_ratio=0.15,
        range_round_trips=40,
        range_total_signals=200,
        median_loss_r=1.1,
        unique_calendar_days=40,
    )
    assert metric == "occupancy"
    assert value is not None
    assert reason is not None and "occupancy" in reason


@pytest.mark.unit
def test_stage2_blocker_insufficient_round_trips() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE2_RANGE,
        stage_trades=250,
        stage_wins=80,
        hold_ratio=0.50,
        required=250,
        constitution_violations=0,
        range_flat_ratio=0.50,
        range_round_trips=2,
        range_total_signals=200,
        median_loss_r=1.1,
        unique_calendar_days=40,
    )
    assert metric == "round_trips"
    assert reason is not None and "round_trips" in reason


@pytest.mark.unit
def test_stage3_blocker_constitution_violations() -> None:
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE3_MIXED,
        stage_trades=400,
        stage_wins=80,
        hold_ratio=0.40,
        required=400,
        constitution_violations=2,
        range_flat_ratio=0.50,
        range_round_trips=40,
        range_total_signals=100,
        median_loss_r=1.1,
        unique_calendar_days=40,
    )
    assert metric == "constitution_violations"
    assert reason is not None and "constitution" in reason
