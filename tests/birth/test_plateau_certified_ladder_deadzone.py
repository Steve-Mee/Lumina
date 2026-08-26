"""Certified plateau ladder dead-zone: execute or terminal (post-mortem 2026-08-10).

Root cause: begin_evolution_step used starship certified max_steps=4 while
terminal/trigger predicates used full ladder (6) / plateau_max_evolution_steps (8),
so the run could neither advance nor terminal-stall — pure thrash.
"""

from __future__ import annotations

import time

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    PlateauState,
    begin_evolution_step,
    evolution_ladder_exhausted,
    progress_fields,
    should_force_advance_evolution_step,
    should_terminal_plateau_stall,
    should_trigger_plateau_evolution_step,
)
from lumina_core.birth.starship_swarm_gates import effective_plateau_max_evolution_steps


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = dict(
        plateau_detection_enabled=True,
        plateau_max_evolution_steps=8,
        starship_certified_plateau_max_evolution_steps=4,
        plateau_evolution_min_ppo_steps_between_steps=15_000,
        plateau_evolution_max_rollouts_per_step=24,
        plateau_evolution_rollouts_per_step=12,
        beyond_gate_evolution_rollouts_per_step=4,
        plateau_max_wall_sec=7200,
        stall_remediation_enabled=True,
        stall_remediation_max_cycles=3,
        stall_remediation_max_steps=5,
    )
    base.update(overrides)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_certified_max_steps_ssot() -> None:
    cfg = _cfg()
    assert effective_plateau_max_evolution_steps(cfg, certified=True) == 4
    assert effective_plateau_max_evolution_steps(cfg, certified=False) == 8


@pytest.mark.unit
def test_live_step4_terminals_with_certified_max() -> None:
    """Reproduce paused run: step=4, certified max=4, expectancy stall, beyond gate."""
    cfg = _cfg()
    max_steps = effective_plateau_max_evolution_steps(cfg, certified=True)
    state = PlateauState(
        active=True,
        evolution_step=4,
        evolution_rollouts_this_step=16,
        plateau_started_at=time.time() - 1100,
        winrate_at_step_start=0.28,
        best_winrate=0.285,
        best_winrate_at_cycle_start=0.285,
    )
    assert evolution_ladder_exhausted(state, max_steps=max_steps) is True
    assert evolution_ladder_exhausted(state) is False  # full ladder still open
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
    # Without max_steps: historical dead zone (must not regress callers that pass max).
    assert (
        should_terminal_plateau_stall(
            state,
            stage_trades=712,
            required=300,
            cfg=cfg,
            meta_self_eval_phase="",
            remediation_exhausted=True,
            trade_budget_remaining=24_000,
        )
        is False
    )
    assert (
        should_trigger_plateau_evolution_step(
            state,
            cfg=cfg,
            current_winrate=0.247,
            allow_start=False,
            max_steps=max_steps,
        )
        is False
    )
    action = begin_evolution_step(
        state, stage_trades=712, stage_wins=176, max_steps=max_steps
    )
    assert action == EvolutionAction.TERMINAL


@pytest.mark.unit
def test_force_advance_ignores_min_ppo_after_max_rollouts() -> None:
    cfg = _cfg(plateau_evolution_min_ppo_steps_between_steps=50_000)
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=24,
        winrate_at_step_start=0.268,
    )
    assert (
        should_force_advance_evolution_step(
            state,
            cfg=cfg,
            current_winrate=0.268,
            pass_target=0.35,
            ppo_steps_since_step_start=100,
            stage_trades=100,  # not past gate → uncompressed max=24
            required=300,
        )
        is True
    )


@pytest.mark.unit
def test_beyond_pass_gate_compresses_force_threshold() -> None:
    """Past volume gate (not only 3× hard-stop) must compress rollout waits."""
    cfg = _cfg()
    state = PlateauState(
        active=True,
        evolution_step=2,
        evolution_rollouts_this_step=8,  # compressed max = 4*2 = 8
        winrate_at_step_start=0.28,
        plateau_started_at=time.time(),
    )
    assert (
        should_force_advance_evolution_step(
            state,
            cfg=cfg,
            current_winrate=0.27,
            pass_target=0.35,
            ppo_steps_since_step_start=50,
            stage_trades=412,  # past required=300, far from 3× hard-stop
            required=300,
        )
        is True
    )


@pytest.mark.unit
def test_progress_fields_use_effective_max_steps() -> None:
    cfg = _cfg()
    state = PlateauState(active=True, evolution_step=4, plateau_started_at=time.time())
    fields = progress_fields(
        state, stage_trades=712, required=300, cfg=cfg, max_steps=4
    )
    assert fields["evolution_phase"] == "exhausted"
    assert fields["evolution_actions_total"] == 4
    assert fields["evolution_actions_completed"] == 4
    assert fields["evolution_actions_remaining"] == 0
    assert fields["plateau_evolution_max_steps_effective"] == 4


@pytest.mark.unit
def test_beyond_gate_soft_advance_ignores_min_ppo() -> None:
    """Past volume gate: soft advance must not wait for 15k PPO steps."""
    from lumina_core.birth.plateau_escalator import should_advance_evolution_step

    cfg = _cfg(plateau_evolution_min_ppo_steps_between_steps=15_000)
    state = PlateauState(
        active=True,
        evolution_step=2,
        evolution_rollouts_this_step=4,  # compressed min rollouts
        winrate_at_step_start=0.28,
    )
    assert (
        should_advance_evolution_step(
            state,
            cfg=cfg,
            current_winrate=0.27,
            pass_target=0.35,
            ppo_steps_since_step_start=50,
            stage_trades=400,
            required=300,
        )
        is True
    )


@pytest.mark.unit
def test_brake_no_lift_respects_certified_max() -> None:
    from lumina_core.birth.plateau_escalator import should_brake_recovery_no_lift

    state = PlateauState(
        active=True,
        evolution_step=4,
        best_winrate=0.285,
        best_winrate_at_cycle_start=0.285,
    )
    assert should_brake_recovery_no_lift(state, max_steps=4) is True
    assert should_brake_recovery_no_lift(state) is False  # full ladder not done
