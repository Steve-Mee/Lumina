"""Deep-resume must honor certified max_steps (no silent ladder restart)."""

from __future__ import annotations

import time

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    PlateauState,
    evolution_ladder_exhausted,
    sanitize_phantom_evolution_steps,
    should_brake_recovery_no_lift,
    should_terminal_plateau_stall,
)
from lumina_core.birth.starship_swarm_gates import effective_plateau_max_evolution_steps


@pytest.mark.unit
def test_sanitize_phantom_respects_certified_cap() -> None:
    state = PlateauState(active=True, evolution_step=8)
    assert sanitize_phantom_evolution_steps(state, max_steps=4) is True
    assert state.evolution_step == 4


@pytest.mark.unit
def test_live_paused_run_exhaust_predicates_with_empty_history() -> None:
    """Reproduce 2026-08-10: step=4, empty history, certified max=4."""
    cfg = BirthCurriculumConfig(
        plateau_detection_enabled=True,
        plateau_max_evolution_steps=8,
        starship_certified_plateau_max_evolution_steps=4,
        stall_remediation_enabled=True,
        stall_remediation_max_cycles=3,
        stall_remediation_max_steps=5,
    )
    max_steps = effective_plateau_max_evolution_steps(cfg, certified=True)
    state = PlateauState(
        active=True,
        evolution_step=4,
        evolution_history=[],  # telemetry gap — still exhausted
        plateau_started_at=time.time() - 1200,
        best_winrate=0.285,
        best_winrate_at_cycle_start=0.285,
        winrate_at_step_start=0.28,
    )
    assert evolution_ladder_exhausted(state, max_steps=max_steps) is True
    assert should_brake_recovery_no_lift(state, max_steps=max_steps) is True
    assert (
        should_terminal_plateau_stall(
            state,
            stage_trades=712,
            required=300,
            cfg=cfg,
            meta_self_eval_phase="",
            remediation_exhausted=True,
            trade_budget_remaining=24_000,
            max_steps=max_steps,
            stage=CurriculumStage.STAGE2_RANGE,
        )
        is True
    )
    # Without max_steps: historical dead zone must remain visible as False.
    assert evolution_ladder_exhausted(state) is False


@pytest.mark.unit
def test_mid_gate_beyond_not_hard_stop_still_exhausts_certified() -> None:
    """Live path: 412 beyond gate of 900 max is NOT hard-stop, but ladder is done."""
    cfg = BirthCurriculumConfig(
        plateau_detection_enabled=True,
        plateau_max_evolution_steps=8,
        starship_certified_plateau_max_evolution_steps=4,
        plateau_trades_beyond_gate_multiplier=3,
        stall_remediation_enabled=True,
    )
    max_steps = effective_plateau_max_evolution_steps(cfg, certified=True)
    state = PlateauState(
        active=True,
        evolution_step=4,
        evolution_history=[],
        plateau_started_at=time.time() - 1115,
        best_winrate=0.285,
        best_winrate_at_cycle_start=0.285,
    )
    from lumina_core.birth.plateau_enter import should_trades_beyond_gate_hard_stop

    # 712 stage trades, required 300 → beyond 412; hard-stop at 900
    assert should_trades_beyond_gate_hard_stop(712, 300, cfg) is False
    assert evolution_ladder_exhausted(state, max_steps=max_steps) is True
    assert (
        should_terminal_plateau_stall(
            state,
            stage_trades=712,
            required=300,
            cfg=cfg,
            meta_self_eval_phase="",
            remediation_exhausted=True,
            trade_budget_remaining=24_000,
            max_steps=max_steps,
        )
        is True
    )
