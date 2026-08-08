"""Stage2 plateau enters at pass-gate when EdgeScore flat-band fails."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_enter import (
    PlateauEnterContext,
    plateau_min_stage_trades,
    should_enter_plateau,
)


@pytest.mark.unit
def test_stage2_edgescore_plateau_min_is_pass_gate() -> None:
    cfg = BirthCurriculumConfig(
        stage2_range_trades=3000,
        stage_pass_trade_pct=0.10,
        stage2_edgescore_enabled=True,
        plateau_min_stage_trades_pct=0.25,
    )
    # Pass gate 300 (10% of 3000) — not 750 (25% of 3000).
    assert plateau_min_stage_trades(CurriculumStage.STAGE2_RANGE, cfg) == 300


@pytest.mark.unit
def test_stage2_flat_band_fail_enters_plateau_after_volume_gate() -> None:
    cfg = BirthCurriculumConfig(
        stage2_range_trades=3000,
        stage_pass_trade_pct=0.10,
        stage2_edgescore_enabled=True,
        plateau_detection_enabled=True,
        velocity_stall_attempt_threshold=32,
    )
    ctx = PlateauEnterContext(
        stage_trades=400,
        stage_wins=120,
        required=300,
        winrate_trend_slope=0.0,
        velocity_stall_attempts=0,
        meta_self_eval_phase="",
        pass_metric_target=0.45,
        stage=CurriculumStage.STAGE2_RANGE,
        meta_learning_health="flat",
        skill_failing=True,  # flat-band skill fail from detector
        range_flat_ratio=0.96,
    )
    assert should_enter_plateau(ctx, cfg=cfg) is True


@pytest.mark.unit
def test_stage2_without_edgescore_keeps_25pct_floor() -> None:
    cfg = BirthCurriculumConfig(
        stage2_range_trades=3000,
        stage_pass_trade_pct=0.10,
        stage2_edgescore_enabled=False,
        plateau_min_stage_trades_pct=0.25,
    )
    assert plateau_min_stage_trades(CurriculumStage.STAGE2_RANGE, cfg) == 750
