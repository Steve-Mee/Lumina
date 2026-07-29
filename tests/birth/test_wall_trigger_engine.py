"""Unit tests for wall trigger engine."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.wall_trigger_engine import (
    constitution_blocks_adaptation,
    evaluate_adaptation_stuck,
    evaluate_certified_stall,
    evaluate_wall_trigger,
)


@pytest.fixture
def cfg() -> BirthCurriculumConfig:
    return BirthCurriculumConfig(
        stage1_winrate_stagnation_rollouts=2,
        stage2_hold_stagnation_rollouts=2,
        certified_stage_stall_wall_sec=300,
        stage1_trend_trades=100,
    )


@pytest.mark.unit
def test_certified_stall_on_wall_budget_exhausted_without_stagnation(
    cfg: BirthCurriculumConfig,
) -> None:
    """Runbook §6 / Starship: wall exhausted + skill blocker → stall (no 1pp wobble gate)."""
    cfg.stage1_edgescore_enabled = True
    cfg.stage1_winrate_pass_floor = 0.35
    result = evaluate_certified_stall(
        stage=CurriculumStage.STAGE1_TREND,
        stage_trades=500,
        stage_wins=167,  # 33.4%
        required=200,
        hold_ratio=0.62,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
        elapsed_stage_sec=100.0,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
        wall_budget_exhausted=True,
        allow_provisional=False,
        failure_key="stage1_winrate",
        force=False,
        cfg=cfg,
        policy_entropy=0.5,
        ppo_steps=1000,
    )
    assert result.triggered is True
    assert result.trigger_type == "certified_stall"
    assert result.pending.get("blocker_metric")


@pytest.mark.unit
def test_certified_stall_triggers_after_stagnation_and_wall(cfg: BirthCurriculumConfig) -> None:
    result = evaluate_certified_stall(
        stage=CurriculumStage.STAGE1_TREND,
        stage_trades=150,
        stage_wins=45,
        required=100,
        hold_ratio=0.2,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
        elapsed_stage_sec=400.0,
        winrate_stagnation_count=3,
        hold_stagnation_count=0,
        wall_budget_exhausted=False,
        allow_provisional=False,
        failure_key="stage1_winrate",
        force=False,
        cfg=cfg,
    )
    assert result.triggered is True
    assert result.trigger_type == "certified_stall"
    assert result.pending.get("blocker_metric")


@pytest.mark.unit
def test_adaptation_stuck_detected(cfg: BirthCurriculumConfig) -> None:
    result = evaluate_adaptation_stuck(
        stage_trades=200,
        last_adaptation_stage_trades=200,
        trades_beyond_hard_stop=True,
        rollouts_since_last_adaptation=5,
        min_rollouts_since_adaptation=5,
    )
    assert result.triggered is True
    assert result.trigger_type == "adaptation_stuck"


@pytest.mark.unit
def test_adaptation_stuck_not_before_min_rollouts(cfg: BirthCurriculumConfig) -> None:
    """Raptor v10: no stuck until min train laps after adaptation."""
    result = evaluate_adaptation_stuck(
        stage_trades=2000,
        last_adaptation_stage_trades=2000,
        trades_beyond_hard_stop=True,
        rollouts_since_last_adaptation=2,
        min_rollouts_since_adaptation=5,
    )
    assert result.triggered is False


@pytest.mark.unit
def test_adaptation_stuck_after_min_rollouts(cfg: BirthCurriculumConfig) -> None:
    result = evaluate_adaptation_stuck(
        stage_trades=2000,
        last_adaptation_stage_trades=2000,
        trades_beyond_hard_stop=True,
        rollouts_since_last_adaptation=5,
        min_rollouts_since_adaptation=5,
    )
    assert result.triggered is True
    assert result.pending.get("blocker_reason") == "adaptation_loop_blocked"


@pytest.mark.unit
def test_adaptation_stuck_not_when_trades_progressed(cfg: BirthCurriculumConfig) -> None:
    result = evaluate_adaptation_stuck(
        stage_trades=2100,
        last_adaptation_stage_trades=2000,
        trades_beyond_hard_stop=True,
        rollouts_since_last_adaptation=20,
        min_rollouts_since_adaptation=5,
    )
    assert result.triggered is False


@pytest.mark.unit
def test_constitution_blocks_stage3_adaptation() -> None:
    assert constitution_blocks_adaptation(
        stage=CurriculumStage.STAGE3_MIXED,
        constitution_violations=1,
    )
    assert constitution_blocks_adaptation(
        stage=CurriculumStage.STAGE1_TREND,
        constitution_violations=5,
    )
    assert not constitution_blocks_adaptation(
        stage=CurriculumStage.STAGE4_POLISH,
        constitution_violations=5,
    )


@pytest.mark.unit
def test_stage3_constitution_stall_blocks_adaptation(cfg: BirthCurriculumConfig) -> None:
    result = evaluate_wall_trigger(
        stage=CurriculumStage.STAGE3_MIXED,
        stage_trades=500,
        stage_wins=200,
        required=500,
        hold_ratio=0.5,
        constitution_violations=2,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
        elapsed_stage_sec=400.0,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
        wall_budget_exhausted=False,
        allow_provisional=False,
        failure_key="stage3_constitution",
        force=False,
        low_velocity_attempts=0,
        last_adaptation_stage_trades=-1,
        cfg=cfg,
    )
    assert result.triggered is True
    assert result.constitution_blocked is True
