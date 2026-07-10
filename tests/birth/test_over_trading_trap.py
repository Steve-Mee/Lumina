"""Over-trading trap detection for stage 2 range patience."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_escalator import detect_over_trading_trap


@pytest.mark.unit
def test_over_trading_trap_detects_low_flat_high_churn() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    assert detect_over_trading_trap(
        range_flat_ratio=0.04,
        range_round_trips=300,
        required=300,
        velocity_stall=True,
        cfg=cfg,
    )


@pytest.mark.unit
def test_over_trading_trap_not_triggered_when_flat_in_band() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    assert not detect_over_trading_trap(
        range_flat_ratio=0.45,
        range_round_trips=300,
        required=300,
        velocity_stall=True,
        cfg=cfg,
    )


@pytest.mark.unit
def test_over_trading_trap_requires_velocity_stall() -> None:
    cfg = BirthCurriculumConfig(stage2_range_trades=3000)
    assert not detect_over_trading_trap(
        range_flat_ratio=0.04,
        range_round_trips=300,
        required=300,
        velocity_stall=False,
        cfg=cfg,
    )
