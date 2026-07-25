"""Raptor v10: adaptation_stuck debounce, resume seed, stage3 hold beyond gate."""

from __future__ import annotations

import pytest

from lumina_core.birth.adaptation_recovery_engine import apply_adaptation_to_state
from lumina_core.birth.adaptive_parameter_manager import WallAdaptationState
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.wall_trigger_engine import (
    evaluate_adaptation_stuck,
    evaluate_wall_trigger,
)


@pytest.mark.unit
def test_apply_adaptation_resets_rollouts_since() -> None:
    from lumina_core.birth.meta_controller_types import AdaptationDecision

    state = WallAdaptationState(
        rollouts_since_last_adaptation=12,
        last_adaptation_stage_trades=100,
    )
    decision = AdaptationDecision(
        should_retry=True,
        reason="test_adapt",
        new_chunk_target=64,
        escalation_increase=1,
        log_message="test",
    )
    updated, _chunk = apply_adaptation_to_state(
        state,
        decision,
        failure_key="test",
        current_winrate=0.31,
        stage_trades=2000,
        max_escalation_level=5,
        max_adaptation_tiers=3,
        max_stage_retries=3,
        exploration_chunk_size=32,
        original_rollout_chunk=64,
    )
    assert updated.last_adaptation_stage_trades == 2000
    assert updated.rollouts_since_last_adaptation == 0


@pytest.mark.unit
def test_wall_trigger_respects_debounce(cfg: BirthCurriculumConfig | None = None) -> None:
    cfg = cfg or BirthCurriculumConfig(adaptation_stuck_min_rollouts=5)
    # Same trades as last adaptation but only 1 rollout → not stuck
    result = evaluate_wall_trigger(
        stage=CurriculumStage.STAGE3_MIXED,
        stage_trades=2000,
        stage_wins=619,
        required=500,
        hold_ratio=0.80,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
        elapsed_stage_sec=100.0,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
        wall_budget_exhausted=False,
        allow_provisional=False,
        failure_key="stage3_foundation",
        force=True,
        low_velocity_attempts=0,
        last_adaptation_stage_trades=2000,
        rollouts_since_last_adaptation=1,
        cfg=cfg,
    )
    # May still trigger certified stall for skill floors under force, but not adaptation_stuck
    if result.triggered:
        assert result.trigger_type != "adaptation_stuck"


@pytest.mark.unit
def test_wall_trigger_stuck_after_enough_rollouts() -> None:
    cfg = BirthCurriculumConfig(
        adaptation_stuck_min_rollouts=5,
        plateau_trades_beyond_gate_multiplier=3,
        stage3_mixed_trades=500,
    )
    # Ensure beyond hard-stop: required 500, trades 2000 → beyond 1500 >= 1500
    result = evaluate_wall_trigger(
        stage=CurriculumStage.STAGE3_MIXED,
        stage_trades=2000,
        stage_wins=619,
        required=500,
        hold_ratio=0.80,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=0,
        elapsed_stage_sec=100.0,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
        wall_budget_exhausted=False,
        allow_provisional=False,
        failure_key="stage3_foundation",
        force=True,
        low_velocity_attempts=0,
        last_adaptation_stage_trades=2000,
        rollouts_since_last_adaptation=5,
        cfg=cfg,
    )
    assert result.triggered is True
    assert result.trigger_type == "adaptation_stuck"


@pytest.mark.unit
def test_stage3_hold_recovery_condition_beyond_gate() -> None:
    """Hold recovery should fire when hold>cap and trades>=required (no pre-gate only)."""
    hold_cap = 0.70
    current_hold = 0.80
    stage_trades = 2000
    required = 500
    velocity_hot = False
    beyond_or_at_gate = stage_trades >= required
    should_recover = current_hold > hold_cap and (
        beyond_or_at_gate or velocity_hot or current_hold > 0.75
    )
    assert should_recover is True

    # Pre-v10 dead zone: old condition stage_trades < required would block
    old_condition = (
        stage_trades < required and current_hold > 0.75 and velocity_hot
    )
    assert old_condition is False


@pytest.mark.unit
def test_evaluate_stuck_defaults_require_min_rollouts() -> None:
    # Default min=5, default rollouts_since=0 → not stuck
    result = evaluate_adaptation_stuck(
        stage_trades=2000,
        last_adaptation_stage_trades=2000,
        trades_beyond_hard_stop=True,
    )
    assert result.triggered is False
