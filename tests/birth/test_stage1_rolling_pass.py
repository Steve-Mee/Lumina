"""Stage1 can pass on rolling window winrate (Raptor experimental birth)."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_stage1_pass_on_rolling_when_lifetime_below_gate() -> None:
    cfg = _cfg(
        stage1_edgescore_enabled=False,
        stage1_use_rolling_pass=True,
        stage1_rolling_pass_window=500,
        stage1_winrate_pass_threshold=0.45,
        stage1_winrate_pass_floor=0.45,
        stage_pass_trade_pct=0.10,
        stage1_trend_trades=2000,
    )
    # lifetime 39%, rolling 46% over last 500 — should pass
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=2000,
        wins=780,  # 39%
        hold_signals=100,
        total_signals=1000,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
        rolling_winrate=0.46,
    )
    assert result.passed is True
    assert "source=rolling" in result.message


@pytest.mark.unit
def test_stage1_fail_when_both_below_gate() -> None:
    cfg = _cfg(
        stage1_edgescore_enabled=False,
        stage1_use_rolling_pass=True,
        stage1_rolling_pass_window=500,
    )
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=2000,
        wins=780,
        hold_signals=100,
        total_signals=1000,
        constitution_violations=0,
        target_trades=2000,
        cfg=cfg,
        rolling_winrate=0.39,
    )
    assert result.passed is False


@pytest.mark.unit
def test_stage1_still_requires_zero_constitution() -> None:
    cfg = _cfg(stage1_edgescore_enabled=False, stage1_use_rolling_pass=True)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE1_TREND,
        trades=2000,
        wins=1000,
        hold_signals=100,
        total_signals=1000,
        constitution_violations=3,
        target_trades=2000,
        cfg=cfg,
        rolling_winrate=0.50,
    )
    assert result.passed is False
