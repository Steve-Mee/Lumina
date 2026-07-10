"""Regression: beyond-gate plateau entry and expansion skip at max ladder."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    PlateauEnterContext,
    adaptation_stuck_escape_allowed,
    plateau_max_trades_beyond_gate,
    plateau_trades_beyond_gate,
    should_enter_plateau,
    should_trades_beyond_gate_hard_stop,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_trades_beyond_gate_hard_stop_at_847_stage1() -> None:
    cfg = _cfg(plateau_trades_beyond_gate_multiplier=3)
    required = 200
    stage_trades = 847
    assert plateau_trades_beyond_gate(stage_trades, required) == 647
    assert plateau_max_trades_beyond_gate(required, cfg) == 600
    assert should_trades_beyond_gate_hard_stop(stage_trades, required, cfg) is True


@pytest.mark.unit
def test_beyond_gate_enters_plateau_despite_improving_slope() -> None:
    cfg = _cfg(
        plateau_min_stage_trades_pct=0.25,
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.10,
        velocity_stall_epsilon=0.002,
    )
    ctx = PlateauEnterContext(
        stage_trades=847,
        stage_wins=251,
        required=200,
        winrate_trend_slope=0.015,
        velocity_stall_attempts=0,
        meta_self_eval_phase="idle",
        pass_metric_target=0.40,
        plateau_quarantine_active=False,
        stage=CurriculumStage.STAGE1_TREND,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is True


@pytest.mark.unit
def test_adaptation_stuck_escape_allowed_with_budget() -> None:
    assert adaptation_stuck_escape_allowed(
        escapes_used=0,
        max_escapes=3,
        trade_budget_remaining=1000,
    )
    assert adaptation_stuck_escape_allowed(
        escapes_used=2,
        max_escapes=3,
        trade_budget_remaining=1,
    )


@pytest.mark.unit
def test_adaptation_stuck_escape_blocked_when_exhausted_or_no_budget() -> None:
    assert not adaptation_stuck_escape_allowed(
        escapes_used=3,
        max_escapes=3,
        trade_budget_remaining=1000,
    )
    assert not adaptation_stuck_escape_allowed(
        escapes_used=0,
        max_escapes=3,
        trade_budget_remaining=0,
    )
