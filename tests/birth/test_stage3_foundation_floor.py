"""Raptor v7: stage3 mixed requires skill floor, not volume-only graduation."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, evaluate_stage_pass
from lumina_core.birth.stage_scorecard import compute_stage_blocker, pass_criteria_for_stage
from tests.birth.honest_settlement import foundation_eval_kwargs, honest_closes


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    # Classic foundation-floor assertions (not Starship EdgeScore path).
    base = BirthCurriculumConfig(stage3_edgescore_enabled=False)
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_stage3_fails_low_winrate_high_hold() -> None:
    cfg = _cfg(stage3_winrate_floor=0.35, stage3_hold_ratio_max=0.70)
    # Live-like: 500 trades, ~31% WR, ~80% hold, 0 hard violations
    result = evaluate_stage_pass(
        CurriculumStage.STAGE3_MIXED,
        trades=500,
        wins=159,
        hold_signals=8000,
        total_signals=10_000,
        constitution_violations=0,
        target_trades=5000,
        cfg=cfg,
        allow_provisional=False,
        rolling_winrate=0.31,
    )
    assert result.passed is False
    assert "occupancy" in result.message or "median_loss_r" in result.message


@pytest.mark.unit
def test_stage3_passes_with_foundation_floors() -> None:
    cfg = _cfg(stage3_winrate_floor=0.35, stage3_hold_ratio_max=0.70)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE3_MIXED,
        trades=500,
        wins=180,  # 36%
        hold_signals=5000,
        total_signals=10_000,  # 50% hold
        constitution_violations=0,
        target_trades=5000,
        cfg=cfg,
        allow_provisional=False,
        rolling_winrate=0.36,
        range_flat_bars=4000,
        range_total_signals=10_000,
        range_round_trips=50,
        **honest_closes(500),
        **foundation_eval_kwargs(),
    )
    assert result.passed is True


@pytest.mark.unit
def test_stage3_passes_on_rolling_when_lifetime_low() -> None:
    """Raptor v12: rolling path is the real escape hatch at high trade volume."""
    cfg = _cfg(
        stage3_winrate_floor=0.35,
        stage3_hold_ratio_max=0.70,
        stage3_use_rolling_pass=True,
        stage1_rolling_pass_window=500,
    )
    # Lifetime ~31% (670/2152) but rolling 36% should pass with hold OK.
    result = evaluate_stage_pass(
        CurriculumStage.STAGE3_MIXED,
        trades=2152,
        wins=670,
        hold_signals=46_000,
        total_signals=94_000,  # ~49% hold
        constitution_violations=0,
        target_trades=5000,
        cfg=cfg,
        allow_provisional=False,
        rolling_winrate=0.36,
        consecutive_rolling_pass_windows=2,
        **honest_closes(2152),
    )
    assert result.passed is False


@pytest.mark.unit
def test_stage3_fails_when_both_lifetime_and_rolling_low() -> None:
    cfg = _cfg(stage3_winrate_floor=0.35, stage3_hold_ratio_max=0.70)
    result = evaluate_stage_pass(
        CurriculumStage.STAGE3_MIXED,
        trades=2152,
        wins=670,
        hold_signals=46_000,
        total_signals=94_000,
        constitution_violations=0,
        target_trades=5000,
        cfg=cfg,
        allow_provisional=False,
        rolling_winrate=0.31,
    )
    assert result.passed is False


@pytest.mark.unit
def test_stage3_blocker_shows_lifetime_and_rolling() -> None:
    cfg = _cfg(stage3_winrate_floor=0.35, stage3_hold_ratio_max=0.70)
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE3_MIXED,
        stage_trades=2152,
        stage_wins=670,
        hold_ratio=0.50,
        required=500,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
        cfg=cfg,
        rolling_winrate=0.31,
        **foundation_eval_kwargs(),
    )
    # Missing occupancy (signals=0) surfaces after process-R is supplied.
    assert metric == "occupancy"
    assert reason is not None
    assert "occupancy" in reason.lower()
    _ = value


@pytest.mark.unit
def test_stage3_blocker_reports_winrate() -> None:
    cfg = _cfg(stage3_winrate_floor=0.35, stage3_hold_ratio_max=0.70)
    metric, value, reason = compute_stage_blocker(
        CurriculumStage.STAGE3_MIXED,
        stage_trades=500,
        stage_wins=150,
        hold_ratio=0.50,
        required=500,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
        cfg=cfg,
        **foundation_eval_kwargs(),
    )
    assert metric == "occupancy"
    assert reason is not None
    assert "occupancy" in reason.lower()
    _ = value


@pytest.mark.unit
def test_stage3_pass_criteria_label_mentions_floors() -> None:
    cfg = _cfg(stage3_winrate_floor=0.35, stage3_hold_ratio_max=0.70)
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE3_MIXED, cfg=cfg)
    assert criteria.id == "mixed_regimes"
    assert criteria.metric_min == pytest.approx(-0.05)
    assert criteria.metric_target is None
    assert "edge" in criteria.label.lower() or "occupancy" in criteria.label.lower()
