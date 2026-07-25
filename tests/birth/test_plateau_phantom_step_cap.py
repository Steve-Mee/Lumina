"""Plateau phantom-step cap + stall remediation deadlock fixes."""

from __future__ import annotations

import time

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_escalator import (
    EVOLUTION_STEP_ACTIONS,
    EvolutionAction,
    PlateauState,
    begin_evolution_step,
    evolution_ladder_exhausted,
    evolution_phantom_steps,
    sanitize_phantom_evolution_steps,
    should_block_plateau_recovery,
    should_terminal_plateau_stall,
    should_trigger_plateau_evolution_step,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = dict(
        plateau_detection_enabled=True,
        plateau_max_evolution_steps=8,
        plateau_evolution_rollouts_per_step=12,
        plateau_evolution_max_rollouts_per_step=24,
        plateau_max_wall_sec=7200,
        plateau_trades_beyond_gate_multiplier=3,
        stall_remediation_enabled=True,
        stall_remediation_max_cycles=3,
        stall_remediation_max_steps=5,
    )
    base.update(overrides)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_phantom_steps_capped_on_begin_evolution_step() -> None:
    state = PlateauState(active=True, evolution_step=6)
    action = begin_evolution_step(state, stage_trades=9000, stage_wins=2700)
    assert action == EvolutionAction.TERMINAL
    assert state.evolution_step == len(EVOLUTION_STEP_ACTIONS)
    assert evolution_ladder_exhausted(state)


@pytest.mark.unit
def test_legacy_step_38_sanitized_to_six() -> None:
    state = PlateauState(active=True, evolution_step=38)
    assert sanitize_phantom_evolution_steps(state) is True
    assert state.evolution_step == len(EVOLUTION_STEP_ACTIONS)
    assert evolution_phantom_steps(state) == 0


@pytest.mark.unit
def test_no_trigger_after_ladder_exhausted() -> None:
    cfg = _cfg()
    state = PlateauState(
        active=True,
        evolution_step=len(EVOLUTION_STEP_ACTIONS),
        evolution_rollouts_this_step=24,
    )
    assert should_trigger_plateau_evolution_step(
        state, cfg=cfg, current_winrate=0.29, allow_start=False
    ) is False


@pytest.mark.unit
def test_terminal_fires_when_ladder_exhausted_despite_remediation_available() -> None:
    """Regression: stall remediation deadlock (cycle 0 blocked terminal forever)."""
    cfg = _cfg()
    state = PlateauState(active=True, evolution_step=6, plateau_started_at=time.time() - 100)
    assert should_terminal_plateau_stall(
        state,
        stage_trades=900,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="committed",
        remediation_exhausted=False,
        trade_budget_remaining=5000,
    ) is True


@pytest.mark.unit
def test_should_block_recovery_when_ladder_exhausted() -> None:
    cfg = _cfg()
    state = PlateauState(active=True, evolution_step=6)
    assert should_block_plateau_recovery(
        state,
        cfg=cfg,
        remediation_exhausted=False,
        trade_budget_remaining=5000,
        stage_trades=900,
        required=200,
    ) is True


@pytest.mark.unit
def test_trades_beyond_gate_hard_stop_triggers_terminal_when_ladder_done() -> None:
    """Raptor v3: hard-stop alone mid-ladder is not terminal; ladder-done is."""
    from lumina_core.birth.plateau_escalator import EVOLUTION_STEP_ACTIONS

    cfg = _cfg(plateau_trades_beyond_gate_multiplier=3)
    mid = PlateauState(active=True, evolution_step=2, plateau_started_at=time.time())
    assert should_terminal_plateau_stall(
        mid,
        stage_trades=800,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="",
        remediation_exhausted=False,
        trade_budget_remaining=5000,
    ) is False
    done = PlateauState(
        active=True,
        evolution_step=len(EVOLUTION_STEP_ACTIONS),
        plateau_started_at=time.time(),
    )
    assert should_terminal_plateau_stall(
        done,
        stage_trades=800,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="",
        remediation_exhausted=False,
        trade_budget_remaining=5000,
    ) is True


@pytest.mark.unit
def test_evolution_actions_count_matches_ladder() -> None:
    assert len(EVOLUTION_STEP_ACTIONS) == 6
