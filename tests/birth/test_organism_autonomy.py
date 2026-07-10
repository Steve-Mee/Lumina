"""Organism Autonomy Engine tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.death_spiral_guard import (
    DeathSpiralState,
    record_stall_signature,
    reset_after_novelty,
)
from lumina_core.birth.organism_autonomy import (
    OrganismAutonomyState,
    RecoveryDispatch,
    evaluate_terminal_stall,
    map_recommended_to_service_action,
)
from lumina_core.birth.phoenix_loop import (
    PHOENIX_CYCLE_REASON,
    PhoenixLoopState,
    select_phoenix_novelty,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = dict(
        autonomous_recovery_enabled=True,
        phoenix_loop_enabled=True,
        phoenix_max_cycles=12,
        allow_provisional_pass=True,
        graduation_mode="evolution_deferred",
        provisional_oos_floor=0.35,
        stage1_winrate_pass_floor=0.35,
        death_spiral_repeat_threshold=3,
        death_spiral_novelty_budget=2,
    )
    base.update(overrides)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_map_recommended_actions() -> None:
    assert map_recommended_to_service_action("expand_data") == "expand_and_retry"
    assert map_recommended_to_service_action("phoenix_reset") == "phoenix_recovery"
    assert map_recommended_to_service_action("unknown") == "resume_stalled_stage"


@pytest.mark.unit
def test_phoenix_cycle_selects_novelty() -> None:
    state = PhoenixLoopState(phoenix_count=2)
    novelty = select_phoenix_novelty(state, cfg=_cfg())
    assert novelty.value in {"expand_data", "policy_swarm", "reward_sweep", "soft_gate", "widen_horizon"}


@pytest.mark.unit
def test_death_spiral_circuit_breaker() -> None:
    state = DeathSpiralState()
    cfg = _cfg(death_spiral_repeat_threshold=2)
    assert record_stall_signature(
        state,
        curriculum_stage="stage1_trend",
        blocker_metric="trend_winrate",
        blocker_value=0.41,
        cfg=cfg,
    ) is False
    tripped = record_stall_signature(
        state,
        curriculum_stage="stage1_trend",
        blocker_metric="trend_winrate",
        blocker_value=0.41,
        cfg=cfg,
    )
    assert tripped is True
    reset_after_novelty(state, cfg=cfg)
    assert state.circuit_breaker_tripped is False


@pytest.mark.unit
def test_evaluate_terminal_stall_phoenix_resume() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(),
        autonomy_state=autonomy,
        pending={
            "terminal_stall_reason": "stall_remediation_exhausted",
            "blocker_metric": "trend_winrate",
            "blocker_value": 0.39,
        },
        curriculum_stage="stage1_trend",
        stage_trades=500,
        required=600,
        constitution_violations=0,
        fitness_signal=0.38,
        remediation_cycles_exhausted=True,
        plateau_exhausted=True,
    )
    assert decision.dispatch == RecoveryDispatch.PHOENIX_RESUME
    assert decision.needs_attention is False
    assert decision.retryable is True
    assert decision.stall_reason == PHOENIX_CYCLE_REASON


@pytest.mark.unit
def test_evaluate_terminal_stall_disabled_needs_attention() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(autonomous_recovery_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stall_remediation_exhausted"},
        curriculum_stage="stage1_trend",
        stage_trades=100,
        required=200,
        constitution_violations=0,
        fitness_signal=0.2,
    )
    assert decision.dispatch == RecoveryDispatch.TERMINAL_NOTIFY_ONLY
    assert decision.needs_attention is True