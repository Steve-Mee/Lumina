"""Certified curriculum pass integrity — no provisional/oracle bypass."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass


@pytest.mark.unit
def test_certified_stage1_rejects_oracle_soft_pass() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=120,
        wins=15,
        hold_signals=900,
        total_signals=1000,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
        allow_provisional=False,
        oracle_patterns=500,
        buffer_size=512,
    )
    assert result.passed is False


@pytest.mark.unit
def test_practice_stage1_allows_oracle_soft_pass() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=120,
        wins=15,
        hold_signals=900,
        total_signals=1000,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
        allow_provisional=True,
        oracle_patterns=500,
        buffer_size=512,
    )
    assert result.passed is True
    assert "oracle_soft_pass" in result.message
