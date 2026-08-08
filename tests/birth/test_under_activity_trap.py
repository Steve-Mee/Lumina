"""Stage2 under-activity (chronic flat / over-flat) trap + swarm deferral."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_escalator import (
    detect_under_activity_trap,
    stage2_should_defer_swarm_for_flat_band,
)


@pytest.mark.unit
def test_under_activity_trap_detects_high_flat_past_gate() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    assert detect_under_activity_trap(
        range_flat_ratio=0.956,
        range_total_signals=500,
        stage_trades=1024,
        required=300,
        velocity_stall=False,
        cfg=cfg,
    )


@pytest.mark.unit
def test_under_activity_trap_not_in_band() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    assert not detect_under_activity_trap(
        range_flat_ratio=0.55,
        range_total_signals=500,
        stage_trades=1024,
        required=300,
        velocity_stall=True,
        cfg=cfg,
    )


@pytest.mark.unit
def test_under_activity_trap_requires_signals() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    assert not detect_under_activity_trap(
        range_flat_ratio=0.95,
        range_total_signals=10,
        stage_trades=1024,
        required=300,
        velocity_stall=True,
        cfg=cfg,
    )


@pytest.mark.unit
def test_under_activity_trap_velocity_stall_pre_gate() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    assert detect_under_activity_trap(
        range_flat_ratio=0.90,
        range_total_signals=200,
        stage_trades=100,
        required=300,
        velocity_stall=True,
        cfg=cfg,
    )
    assert not detect_under_activity_trap(
        range_flat_ratio=0.90,
        range_total_signals=200,
        stage_trades=100,
        required=300,
        velocity_stall=False,
        cfg=cfg,
    )


@pytest.mark.unit
def test_stage2_defer_swarm_while_flat_out_of_band() -> None:
    cfg = BirthCurriculumConfig(stage2_flat_band_swarm_defer_steps=2)
    assert stage2_should_defer_swarm_for_flat_band(
        range_flat_ratio=0.956,
        range_total_signals=500,
        stage_trades=1024,
        required=300,
        evolution_step=0,
        cfg=cfg,
    )
    assert stage2_should_defer_swarm_for_flat_band(
        range_flat_ratio=0.956,
        range_total_signals=500,
        stage_trades=1024,
        required=300,
        evolution_step=1,
        cfg=cfg,
    )
    assert not stage2_should_defer_swarm_for_flat_band(
        range_flat_ratio=0.956,
        range_total_signals=500,
        stage_trades=1024,
        required=300,
        evolution_step=2,
        cfg=cfg,
    )


@pytest.mark.unit
def test_stage2_no_defer_when_flat_in_band() -> None:
    cfg = BirthCurriculumConfig(stage2_flat_band_swarm_defer_steps=2)
    assert not stage2_should_defer_swarm_for_flat_band(
        range_flat_ratio=0.45,
        range_total_signals=500,
        stage_trades=1024,
        required=300,
        evolution_step=0,
        cfg=cfg,
    )
