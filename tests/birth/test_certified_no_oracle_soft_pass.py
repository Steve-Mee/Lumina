"""Raptor v5: certified mode must not graduate via oracle_soft_pass."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.stage_pass_receipt import (
    StagePassReceipt,
    verify_stage_pass_receipt,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_certified_stage1_not_passed_with_many_patterns_low_wr() -> None:
    cfg = _cfg(stage1_winrate_pass_threshold=0.45, stage1_use_rolling_pass=True)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=11_827,
        wins=4_470,  # 37.79%
        hold_signals=1000,
        total_signals=10_000,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
        allow_provisional=False,
        oracle_patterns=1917,
        buffer_size=10_000,
        rolling_winrate=0.3779,
    )
    assert result.passed is False
    assert "oracle_soft_pass" not in result.message


@pytest.mark.unit
def test_practice_oracle_soft_pass_marks_provisional() -> None:
    cfg = _cfg()
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=500,
        wins=150,  # 30%
        hold_signals=100,
        total_signals=1000,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
        allow_provisional=True,
        provisional=False,
        oracle_patterns=200,
        buffer_size=500,
        rolling_winrate=0.30,
    )
    assert result.passed is True
    assert result.provisional is True
    assert "oracle_soft_pass" in result.message


@pytest.mark.unit
def test_certified_rejects_soft_oracle_receipt() -> None:
    cfg = _cfg()
    receipt = StagePassReceipt(
        stage="stage1_trend",
        trades=11827,
        wins=4470,
        winrate=0.377949,
        required_trades=200,
        pass_criteria_id="trend_winrate",
        provisional=False,
        passed_at="2026-07-25T08:07:18+00:00",
        engine_version="BRO-v2",
        message="trend winrate=37.79% gate=45% source=neither oracle_soft_pass",
        winrate_gate=0.45,
    )
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE1_TREND,
        receipt,
        cfg=cfg,
        training_mode="certified",
    )
    assert ok is False
    assert "soft_oracle" in reason or "winrate" in reason


@pytest.mark.unit
def test_certified_stage2_soft_receipt_rejected() -> None:
    cfg = _cfg()
    receipt = StagePassReceipt(
        stage="stage2_range",
        trades=80,
        wins=26,
        winrate=0.325,
        required_trades=300,
        pass_criteria_id="range_roundtrip",
        provisional=False,
        passed_at="2026-07-25T08:10:09+00:00",
        engine_version="BRO-v2",
        message="range_flat_ratio=23.86% trades=80/300 oracle_soft_pass",
        winrate_gate=None,
    )
    ok, reason = verify_stage_pass_receipt(
        CurriculumStage.STAGE2_RANGE,
        receipt,
        cfg=cfg,
        training_mode="certified",
    )
    assert ok is False
