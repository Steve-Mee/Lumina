"""Unit tests for adaptation_recovery_engine pure decision logic."""

from __future__ import annotations

import pytest

from lumina_core.birth.adaptation_recovery_engine import (
    apply_adaptation_to_state,
    plan_adaptive_recovery,
    plan_never_stop_recovery,
    resolve_legacy_adaptation_decision,
    resolve_meta_adaptation_decision,
)
from lumina_core.birth.adaptive_parameter_manager import WallAdaptationState
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.meta_controller import (
    AdaptationDecision,
    LearningHealth,
    MetaActionPlan,
    RecoveryStrategy,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = dict(
        adaptation_enabled=True,
        wall_behavior="adaptive",
        exploration_chunk_size=8,
        rollout_chunk_trades=20,
        max_adaptation_tiers=4,
        max_stage_retries=3,
        max_escalation_level=5,
        auto_expand_on_adaptation=True,
        max_adaptation_stuck_escapes=2,
    )
    base.update(overrides)
    return BirthCurriculumConfig(**base)


def _state(**overrides: object) -> WallAdaptationState:
    state = WallAdaptationState()
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


@pytest.mark.unit
def test_resolve_meta_adaptation_decision_uses_plan_adaptation() -> None:
    decision = AdaptationDecision(
        should_retry=True,
        reason="meta_retry",
        new_chunk_target=16,
        escalation_increase=1,
    )
    plan = MetaActionPlan(primary=RecoveryStrategy.HOLD, adaptation=decision)
    result = resolve_meta_adaptation_decision(
        plan,
        adaptation_tier=0,
        retries_this_stage=0,
        exploration_chunk_size=8,
        rollout_chunk_trades=20,
        original_rollout_chunk=250,
    )
    assert result is not None
    assert result.reason == "meta_retry"
    assert result.new_chunk_target == 16


@pytest.mark.unit
def test_resolve_meta_adaptation_decision_stall_escalation_at_boundary() -> None:
    plan = MetaActionPlan(primary=RecoveryStrategy.HOLD, adaptation=None)
    result = resolve_meta_adaptation_decision(
        plan,
        adaptation_tier=0,
        retries_this_stage=0,
        exploration_chunk_size=8,
        rollout_chunk_trades=20,
        original_rollout_chunk=250,
    )
    assert result is not None
    assert result.reason == "stall_escalation"
    assert result.should_retry is True


@pytest.mark.unit
def test_resolve_meta_adaptation_decision_persistent_recovery() -> None:
    plan = MetaActionPlan(primary=RecoveryStrategy.HOLD, adaptation=None)
    result = resolve_meta_adaptation_decision(
        plan,
        adaptation_tier=2,
        retries_this_stage=1,
        exploration_chunk_size=8,
        rollout_chunk_trades=20,
        original_rollout_chunk=250,
    )
    assert result is not None
    assert result.reason == "persistent_recovery"


@pytest.mark.unit
def test_resolve_legacy_adaptation_decision_forces_escalation() -> None:
    cfg = _cfg()
    result = resolve_legacy_adaptation_decision(
        stage_trades=50,
        required=100,
        winrate=0.40,
        winrate_history=[0.40],
        escalation_level=0,
        adaptation_tier=0,
        retries_this_stage=0,
        exploration_chunk_size=8,
        rollout_chunk_trades=20,
        original_rollout_chunk=250,
        cfg=cfg,
    )
    assert result is not None
    assert result.should_retry is True


@pytest.mark.unit
def test_apply_adaptation_to_state_updates_tier_and_history() -> None:
    state = _state(adaptation_tier=0, retries_this_stage=2, escalation_level=0)
    decision = AdaptationDecision(
        should_retry=True,
        reason="test",
        new_chunk_target=12,
        escalation_increase=1,
    )
    new_state, chunk = apply_adaptation_to_state(
        state,
        decision,
        failure_key="stall",
        current_winrate=0.35,
        stage_trades=120,
        max_escalation_level=5,
        max_adaptation_tiers=4,
        max_stage_retries=3,
        exploration_chunk_size=8,
        original_rollout_chunk=250,
    )
    assert chunk == 12
    assert new_state.retries_this_stage == 0
    assert new_state.adaptation_tier == 1
    assert len(new_state.adaptation_history) == 1
    assert new_state.recovery_attempts == 1


@pytest.mark.unit
def test_plan_adaptive_recovery_disabled_returns_terminal() -> None:
    cfg = _cfg(adaptation_enabled=False)
    result = plan_adaptive_recovery(
        cfg=cfg,
        state=_state(),
        failure_key="stall",
        trigger_type="stall",
        stage_trades=100,
        required=200,
        current_winrate=0.3,
        winrate_history=[0.3],
        original_rollout_chunk=250,
        rollout_chunk_trades=20,
        trade_budget_remaining=1000,
        terminal_blocked=False,
        constitution_blocked=False,
    )
    assert result.applied is False
    assert result.dispatch == "terminal_notify_only"


@pytest.mark.unit
def test_plan_adaptive_recovery_stuck_escape_blocked() -> None:
    cfg = _cfg(max_adaptation_stuck_escapes=1)
    state = _state(adaptation_stuck_escapes=1)
    result = plan_adaptive_recovery(
        cfg=cfg,
        state=state,
        failure_key="stall",
        trigger_type="adaptation_stuck",
        stage_trades=100,
        required=200,
        current_winrate=0.3,
        winrate_history=[0.3],
        original_rollout_chunk=250,
        rollout_chunk_trades=20,
        trade_budget_remaining=0,
        terminal_blocked=False,
        constitution_blocked=False,
    )
    assert result.applied is False


@pytest.mark.unit
def test_plan_adaptive_recovery_stuck_escape_applies_phoenix() -> None:
    cfg = _cfg()
    result = plan_adaptive_recovery(
        cfg=cfg,
        state=_state(),
        failure_key="stall",
        trigger_type="adaptation_stuck",
        stage_trades=100,
        required=200,
        current_winrate=0.3,
        winrate_history=[0.3],
        original_rollout_chunk=250,
        rollout_chunk_trades=20,
        trade_budget_remaining=500,
        terminal_blocked=False,
        constitution_blocked=False,
    )
    assert result.applied is True
    assert result.recovery_kind == "stuck_escape"
    assert result.spawn_phoenix_reset is True
    assert result.spawn_plateau is True
    assert result.mine_aggressive is True


@pytest.mark.unit
def test_plan_adaptive_recovery_with_meta_plan() -> None:
    cfg = _cfg()
    adapt = AdaptationDecision(
        should_retry=True,
        reason="meta",
        new_chunk_target=16,
        escalation_increase=1,
    )
    plan = MetaActionPlan(
        primary=RecoveryStrategy.EXPLORE_BOOST,
        adaptation=adapt,
        mine=True,
        expand_data=True,
    )
    result = plan_adaptive_recovery(
        cfg=cfg,
        state=_state(),
        failure_key="stall",
        trigger_type="stall",
        stage_trades=150,
        required=100,
        current_winrate=0.28,
        winrate_history=[0.30, 0.29, 0.28],
        original_rollout_chunk=250,
        rollout_chunk_trades=20,
        trade_budget_remaining=500,
        terminal_blocked=False,
        constitution_blocked=False,
        meta_plan=plan,
        learning_health=LearningHealth.DECLINING,
    )
    assert result.applied is True
    assert result.recovery_kind == "adaptive"
    assert result.mine is True
    assert result.expand_data is True
    assert result.parameter_patch is not None


@pytest.mark.unit
def test_plan_never_stop_recovery_forces_continue() -> None:
    cfg = _cfg()
    result = plan_never_stop_recovery(
        cfg=cfg,
        state=_state(adaptation_tier=1),
        failure_key="budget",
        rollout_chunk_trades=20,
        terminal_blocked=False,
    )
    assert result.applied is True
    assert result.recovery_kind == "never_stop"
    assert result.dispatch == "continue_loop"
    assert result.decision is not None
    assert result.decision.reason == "never_stop_forced"
