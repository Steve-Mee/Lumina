"""Raptor fix: beyond-gate must enter plateau even when winrate is in the 35–45% dead zone."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    PlateauEnterContext,
    should_enter_plateau,
    should_trades_beyond_gate_hard_stop,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_live_run_dead_zone_enters_plateau_beyond_hard_stop() -> None:
    """Reproduce 2026-07-24 birth: ~39% WR, 9k trades, gap=0.10 → old code blocked forever."""
    cfg = _cfg(
        plateau_winrate_gap=0.10,
        plateau_trades_beyond_gate_multiplier=3,
        plateau_min_stage_trades_pct=0.25,
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.10,
        velocity_stall_attempt_threshold=99,
    )
    required = 200
    stage_trades = 9087
    stage_wins = 3541  # ~38.97%
    assert should_trades_beyond_gate_hard_stop(stage_trades, required, cfg) is True
    ctx = PlateauEnterContext(
        stage_trades=stage_trades,
        stage_wins=stage_wins,
        required=required,
        winrate_trend_slope=-0.0001,
        velocity_stall_attempts=0,
        meta_self_eval_phase="idle",
        pass_metric_target=0.45,
        plateau_quarantine_active=False,
        stage=CurriculumStage.STAGE1_TREND,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is True


@pytest.mark.unit
def test_near_target_before_beyond_gate_still_waits() -> None:
    """Within gap and not yet beyond hard stop → no plateau (still improving window)."""
    cfg = _cfg(
        plateau_winrate_gap=0.10,
        plateau_trades_beyond_gate_multiplier=3,
        plateau_min_stage_trades_pct=0.05,
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.10,
        velocity_stall_attempt_threshold=1,
    )
    ctx = PlateauEnterContext(
        stage_trades=250,
        stage_wins=100,  # 40% — within gap of 45%
        required=200,
        winrate_trend_slope=0.0,
        velocity_stall_attempts=5,
        meta_self_eval_phase="exhausted",
        pass_metric_target=0.45,
        plateau_quarantine_active=False,
        stage=CurriculumStage.STAGE1_TREND,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is False


@pytest.mark.unit
def test_at_or_above_pass_target_never_enters_plateau() -> None:
    cfg = _cfg(plateau_trades_beyond_gate_multiplier=3)
    ctx = PlateauEnterContext(
        stage_trades=9000,
        stage_wins=4500,  # 50%
        required=200,
        winrate_trend_slope=0.0,
        velocity_stall_attempts=99,
        meta_self_eval_phase="exhausted",
        pass_metric_target=0.45,
        plateau_quarantine_active=False,
        stage=CurriculumStage.STAGE1_TREND,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is False


@pytest.mark.unit
def test_wall_exhausted_hygiene_fail_enters_plateau_without_beyond_gate() -> None:
    """Starship: wall + sub-35% hygiene must enter theater (no vanity-45% wait)."""
    cfg = _cfg(
        plateau_winrate_gap=0.10,
        plateau_trades_beyond_gate_multiplier=3,
        plateau_min_stage_trades_pct=0.25,
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.10,
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        velocity_stall_attempt_threshold=99,
    )
    ctx = PlateauEnterContext(
        stage_trades=500,
        stage_wins=167,  # 33.4%
        required=200,
        winrate_trend_slope=0.0006,
        velocity_stall_attempts=13,
        meta_self_eval_phase="idle",
        pass_metric_target=0.45,
        plateau_quarantine_active=False,
        stage=CurriculumStage.STAGE1_TREND,
        wall_budget_exhausted=True,
        meta_learning_health="flat",
        skill_failing=True,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is True


@pytest.mark.unit
def test_flat_health_beyond_zero_hygiene_fail_enters_plateau() -> None:
    cfg = _cfg(
        plateau_min_stage_trades_pct=0.25,
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.10,
        stage1_edgescore_enabled=True,
        stage1_winrate_pass_floor=0.35,
        velocity_stall_attempt_threshold=99,
    )
    ctx = PlateauEnterContext(
        stage_trades=500,
        stage_wins=165,
        required=200,
        winrate_trend_slope=0.0,
        velocity_stall_attempts=0,
        meta_self_eval_phase="idle",
        pass_metric_target=0.45,
        plateau_quarantine_active=False,
        stage=CurriculumStage.STAGE1_TREND,
        wall_budget_exhausted=False,
        meta_learning_health="flat",
        skill_failing=True,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is True
