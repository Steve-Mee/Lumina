"""Tests for configurable curriculum stage pass gates."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage_pass_trades


@pytest.mark.unit
def test_stage_pass_trades_default_matches_ten_percent() -> None:
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=2000,
        stage2_range_trades=3000,
        stage3_mixed_trades=5000,
    )
    assert stage_pass_trades(CurriculumStage.STAGE1_TREND, cfg) == 200
    assert stage_pass_trades(CurriculumStage.STAGE2_RANGE, cfg) == 300
    assert stage_pass_trades(CurriculumStage.STAGE3_MIXED, cfg) == 500


@pytest.mark.unit
def test_stage_pass_trades_higher_pct() -> None:
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.25,
        stage_pass_min_trades=100,
    )
    assert stage_pass_trades(CurriculumStage.STAGE1_TREND, cfg) == 500


@pytest.mark.unit
def test_stage_pass_trades_respects_min_floor() -> None:
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=800,
        stage_pass_trade_pct=0.05,
        stage_pass_min_trades=100,
    )
    assert stage_pass_trades(CurriculumStage.STAGE1_TREND, cfg) == 100
