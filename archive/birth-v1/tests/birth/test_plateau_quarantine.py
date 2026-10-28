"""Plateau quarantine on checkpoint resume and should_enter_plateau gating."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    PlateauEnterContext,
    apply_plateau_quarantine_on_resume,
    plateau_min_stage_trades,
    should_enter_plateau,
    update_plateau_quarantine_after_rollout,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_apply_quarantine_on_resume_sets_grace_fields() -> None:
    cfg = _cfg(plateau_quarantine_rollouts=32, plateau_quarantine_min_trades=500)
    # Without required (or not past hard-stop) → grace period applies.
    q = apply_plateau_quarantine_on_resume(cfg=cfg, stage_trades=250)
    assert q["plateau_quarantine_active"] is True
    assert q["plateau_quarantine_rollouts_remaining"] == 32
    assert q["plateau_quarantine_trades_remaining"] == 500
    assert q["plateau_quarantine_trades_at_resume"] == 250


@pytest.mark.unit
def test_quarantine_skipped_when_beyond_hard_stop() -> None:
    cfg = _cfg(plateau_quarantine_rollouts=32, plateau_quarantine_min_trades=500)
    q = apply_plateau_quarantine_on_resume(
        cfg=cfg, stage_trades=9_098, required=200
    )
    assert q["plateau_quarantine_active"] is False
    assert q["plateau_quarantine_rollouts_remaining"] == 0
    assert q.get("plateau_quarantine_skipped_reason") == "beyond_hard_stop"


@pytest.mark.unit
def test_quarantine_blocks_plateau_entry_until_grace_elapsed() -> None:
    cfg = _cfg(
        velocity_stall_attempt_threshold=3,
        plateau_min_stage_trades_pct=0.25,
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.10,
    )
    ctx = PlateauEnterContext(
        stage_trades=25_000,
        stage_wins=7_500,
        required=200,
        winrate_trend_slope=0.0,
        velocity_stall_attempts=99,
        meta_self_eval_phase="exhausted",
        pass_metric_target=0.45,
        plateau_quarantine_active=True,
        stage=CurriculumStage.STAGE1_TREND,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is False


@pytest.mark.unit
def test_plateau_min_stage_trades_is_25pct_of_budget() -> None:
    cfg = _cfg(stage1_trend_trades=2000, stage_pass_trade_pct=0.10, plateau_min_stage_trades_pct=0.25)
    assert plateau_min_stage_trades(CurriculumStage.STAGE1_TREND, cfg) == 500


@pytest.mark.unit
def test_update_quarantine_decrements_rollouts_then_trades() -> None:
    q = apply_plateau_quarantine_on_resume(cfg=_cfg(), stage_trades=1000)
    assert update_plateau_quarantine_after_rollout(q, stage_trades=1100) is True
    assert q["plateau_quarantine_rollouts_remaining"] == 31
    q["plateau_quarantine_rollouts_remaining"] = 0
    assert update_plateau_quarantine_after_rollout(q, stage_trades=1200) is True
    assert update_plateau_quarantine_after_rollout(q, stage_trades=1600) is False
    assert q["plateau_quarantine_active"] is False


@pytest.mark.unit
def test_should_enter_plateau_respects_min_stage_trades() -> None:
    cfg = _cfg(
        velocity_stall_attempt_threshold=1,
        plateau_min_stage_trades_pct=0.25,
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.10,
    )
    ctx = PlateauEnterContext(
        stage_trades=300,
        stage_wins=90,
        required=200,
        winrate_trend_slope=0.0,
        velocity_stall_attempts=5,
        meta_self_eval_phase="exhausted",
        pass_metric_target=0.45,
        plateau_quarantine_active=False,
        stage=CurriculumStage.STAGE1_TREND,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is False
    ctx.stage_trades = 600
    assert should_enter_plateau(ctx, cfg=cfg) is True


@pytest.mark.unit
def test_should_enter_plateau_beyond_gate_ignores_positive_slope() -> None:
    cfg = _cfg(
        velocity_stall_attempt_threshold=99,
        plateau_min_stage_trades_pct=0.25,
        stage1_trend_trades=2000,
        stage_pass_trade_pct=0.10,
        plateau_trades_beyond_gate_multiplier=3,
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
