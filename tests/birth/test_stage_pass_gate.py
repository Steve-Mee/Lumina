"""Tests for Foundation stage pass trade floors (ADR-0046)."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage_pass_trades
from lumina_core.birth.foundation_metrics import (
    S1_MIN_TRADES,
    S2_MIN_TRADES,
    S3_MIN_TRADES,
    S4_MIN_TRADES,
    S5_MIN_TRADES,
)


@pytest.mark.unit
def test_stage_pass_trades_uses_foundation_floors_not_budget_pct() -> None:
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=2000,
        stage2_range_trades=3000,
        stage3_mixed_trades=5000,
        stage_pass_trade_pct=0.10,
    )
    assert stage_pass_trades(CurriculumStage.STAGE1_TREND, cfg) == S1_MIN_TRADES
    assert stage_pass_trades(CurriculumStage.STAGE2_RANGE, cfg) == S2_MIN_TRADES
    assert stage_pass_trades(CurriculumStage.STAGE3_MIXED, cfg) == S3_MIN_TRADES
    assert stage_pass_trades(CurriculumStage.STAGE4_VIABLE_PLANT, cfg) == S4_MIN_TRADES
    assert stage_pass_trades(CurriculumStage.STAGE5_PROBE_HANDOFF, cfg) == S5_MIN_TRADES


@pytest.mark.unit
def test_stage_pass_trades_ignores_higher_budget_pct() -> None:
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.25,
        stage_pass_min_trades=100,
    )
    assert stage_pass_trades(CurriculumStage.STAGE1_TREND, cfg) == S1_MIN_TRADES


@pytest.mark.unit
def test_stage_pass_trades_does_not_drop_below_foundation_floor() -> None:
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=800,
        stage_pass_trade_pct=0.05,
        stage_pass_min_trades=100,
    )
    assert stage_pass_trades(CurriculumStage.STAGE1_TREND, cfg) == S1_MIN_TRADES
