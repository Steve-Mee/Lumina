from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    evaluate_stage_pass,
    should_gen0_soft_pass,
    stage_pass_trades,
    stage_progress_pct,
)


@pytest.mark.unit
def test_stage_pass_trades_uses_config_not_hard_cap() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    assert stage_pass_trades(CurriculumStage.STAGE1_TREND, cfg) == 200


@pytest.mark.unit
def test_cumulative_stage_pass_after_enough_trades() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=200,
        wins=100,
        hold_signals=10,
        total_signals=200,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
    )
    assert result.passed is True
    assert "200/200" in result.message


@pytest.mark.unit
def test_single_trade_chunk_does_not_pass() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=1,
        wins=1,
        hold_signals=0,
        total_signals=1,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
    )
    assert result.passed is False


@pytest.mark.unit
def test_gen0_soft_pass_requires_buffer_and_trades() -> None:
    cfg = BirthCurriculumConfig(max_rollouts_per_stage=5, gen0_provisional_min_trades=25)
    assert should_gen0_soft_pass(stage_trades=30, buffer_size=300, attempt=5, cfg=cfg) is True
    assert should_gen0_soft_pass(stage_trades=30, buffer_size=100, attempt=5, cfg=cfg) is False
    assert should_gen0_soft_pass(stage_trades=10, buffer_size=300, attempt=5, cfg=cfg) is False


@pytest.mark.unit
def test_stage_progress_pct() -> None:
    cfg = BirthCurriculumConfig(stage1_trend_trades=2000)
    pct = stage_progress_pct(100, cfg, stage=CurriculumStage.STAGE1_TREND)
    assert pct == 50.0
