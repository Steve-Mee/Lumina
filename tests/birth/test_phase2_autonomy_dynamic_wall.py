"""Pure dynamic wall proposal tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.phase2_autonomy.dynamic_wall import (
    STALL_WALL_MULT_MAX,
    STALL_WALL_MULT_MIN,
    apply_wall_adjustment_to_thresholds,
    propose_dynamic_wall_adjustment,
)


@pytest.mark.unit
def test_proposal_clamps_multiplier() -> None:
    prop = propose_dynamic_wall_adjustment(
        stage="STAGE1_TREND",
        stage_trades=50,
        required=200,
        winrate_slope=-0.05,
        winrate_stagnation_count=5,
        elapsed_stage_sec=5000.0,
        base_stall_wall_sec=300.0,
        regime="TREND",
    )
    assert STALL_WALL_MULT_MIN <= prop.stall_wall_sec_multiplier <= STALL_WALL_MULT_MAX
    assert -1 <= prop.stagnation_rollouts_delta <= 2
    assert prop.risk_touching is False


@pytest.mark.unit
def test_range_regime_extends_patience() -> None:
    prop = propose_dynamic_wall_adjustment(
        stage_trades=100,
        required=100,
        regime="RANGE",
        winrate_slope=0.0,
    )
    assert prop.regime == "RANGE"
    assert prop.stall_wall_sec_multiplier >= 1.0
    assert "range_patience" in prop.rationale


@pytest.mark.unit
def test_apply_thresholds_respect_min_wall() -> None:
    prop = propose_dynamic_wall_adjustment(
        stage_trades=10,
        required=100,
        regime="RANGE",
    )
    thr = apply_wall_adjustment_to_thresholds(
        base_stall_wall_sec=300.0,
        base_winrate_stagnation_rollouts=2,
        base_hold_stagnation_rollouts=2,
        proposal=prop,
    )
    assert int(thr["effective_stall_wall_sec"]) >= 300
    assert int(thr["effective_winrate_stagnation_rollouts"]) >= 1


@pytest.mark.unit
def test_uses_cfg_base_wall() -> None:
    cfg = BirthCurriculumConfig(certified_stage_stall_wall_sec=900)
    prop = propose_dynamic_wall_adjustment(
        stage_trades=100,
        required=100,
        cfg=cfg,
    )
    thr = apply_wall_adjustment_to_thresholds(
        base_stall_wall_sec=float(cfg.certified_stage_stall_wall_sec),
        base_winrate_stagnation_rollouts=3,
        base_hold_stagnation_rollouts=3,
        proposal=prop,
    )
    assert int(thr["effective_stall_wall_sec"]) >= 300
