"""Plateau evolution escalator (ADR-0023) + never-stop fixes."""

from __future__ import annotations

import time

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    PlateauState,
    action_for_step,
    can_force_never_stop_recovery,
    detect_hold_trap,
    should_advance_evolution_step,
    should_block_plateau_recovery,
    should_start_evolution_step,
    should_terminal_plateau_stall,
)
from lumina_core.birth.stall_remediation import curate_buffer_top_quartile


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = dict(
        plateau_detection_enabled=True,
        plateau_winrate_gap=0.10,
        plateau_trades_beyond_gate_multiplier=10,
        plateau_max_wall_sec=7200,
        plateau_max_evolution_steps=8,
        plateau_evolution_rollouts_per_step=12,
        max_forced_recoveries_per_plateau=12,
        velocity_stall_attempt_threshold=32,
        velocity_stall_epsilon=0.002,
        stall_remediation_enabled=True,
        stall_remediation_max_cycles=3,
        stall_remediation_max_steps=5,
    )
    base.update(overrides)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_meta_exhausted_beyond_gate_does_not_terminal_before_evolution() -> None:
    cfg = _cfg(plateau_max_evolution_steps=8)
    state = PlateauState(active=True, evolution_step=0, plateau_started_at=time.time() - 9000)
    assert should_terminal_plateau_stall(
        state,
        stage_trades=6113,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="exhausted",
        remediation_exhausted=False,
        trade_budget_remaining=18_887,
    ) is False
    assert should_block_plateau_recovery(
        state,
        cfg=cfg,
        remediation_exhausted=False,
        trade_budget_remaining=18_887,
    ) is False


@pytest.mark.unit
def test_should_start_evolution_immediately_on_plateau() -> None:
    state = PlateauState(active=True, evolution_step=0, forced_recoveries_count=0)
    assert should_start_evolution_step(state) is True


@pytest.mark.unit
def test_evolution_ladder_actions_include_oracle_and_phoenix() -> None:
    assert action_for_step(1) == EvolutionAction.EXPAND_DATA
    assert action_for_step(5) == EvolutionAction.ORACLE_DISTILL
    assert action_for_step(6) == EvolutionAction.PHOENIX_RESET
    assert action_for_step(7) == EvolutionAction.TERMINAL


@pytest.mark.unit
def test_should_advance_evolution_without_forced_recovery_prerequisite() -> None:
    cfg = _cfg(plateau_evolution_rollouts_per_step=12)
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=12,
        winrate_at_step_start=0.33,
        forced_recoveries_count=0,
    )
    assert should_advance_evolution_step(state, cfg=cfg, current_winrate=0.331) is True


@pytest.mark.unit
def test_detect_hold_trap() -> None:
    cfg = _cfg()
    assert detect_hold_trap(
        hold_ratio=0.62,
        winrate=0.28,
        pass_metric_target=0.45,
        velocity_stall=True,
        cfg=cfg,
    )
    assert not detect_hold_trap(
        hold_ratio=0.40,
        winrate=0.28,
        pass_metric_target=0.45,
        velocity_stall=True,
        cfg=cfg,
    )


@pytest.mark.unit
def test_curate_buffer_top_quartile() -> None:
    class _Buf:
        trajectories = [
            {"reward": 1.0},
            {"reward": 2.0},
            {"reward": 3.0},
            {"reward": 4.0},
        ]
        priorities: list[float] = []

    buf = _Buf()
    removed = curate_buffer_top_quartile(buf, keep_pct=0.25)
    assert removed == 3
    assert len(buf.trajectories) == 1
    assert buf.trajectories[0]["reward"] == 4.0


@pytest.mark.unit
def test_terminal_only_when_evolution_and_budget_exhausted() -> None:
    cfg = _cfg(plateau_max_evolution_steps=8, stall_remediation_enabled=True)
    state = PlateauState(active=True, evolution_step=8)
    assert should_terminal_plateau_stall(
        state,
        stage_trades=6113,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="exhausted",
        remediation_exhausted=True,
        trade_budget_remaining=0,
    ) is True
    assert should_terminal_plateau_stall(
        state,
        stage_trades=6113,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="exhausted",
        remediation_exhausted=False,
        trade_budget_remaining=18_887,
    ) is False


@pytest.mark.unit
def test_should_phoenix_reset_after_failed_cycles() -> None:
    from lumina_core.birth.plateau_escalator import should_phoenix_reset

    state = PlateauState(active=True, full_recovery_cycles=3)
    assert should_phoenix_reset(state, cfg=_cfg(), winrate=0.25) is True
    assert should_phoenix_reset(state, cfg=_cfg(), winrate=0.35) is False


@pytest.mark.unit
def test_can_force_never_stop_while_forced_budget_remains() -> None:
    state = PlateauState(active=True, forced_recoveries_count=2)
    assert can_force_never_stop_recovery(state, cfg=_cfg(max_forced_recoveries_per_plateau=12)) is True
    state.forced_recoveries_count = 12
    assert can_force_never_stop_recovery(state, cfg=_cfg(max_forced_recoveries_per_plateau=12)) is False
