"""Raptor v3: hard-stop must not block mid-ladder; terminal after ladder or compressed wall."""

from __future__ import annotations

import time

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_escalator import (
    PlateauState,
    evolution_ladder_exhausted,
    should_block_plateau_recovery,
    should_force_advance_evolution_step,
    should_terminal_plateau_stall,
    EVOLUTION_STEP_ACTIONS,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_hard_stop_does_not_block_mid_ladder_recovery() -> None:
    cfg = _cfg(plateau_trades_beyond_gate_multiplier=3, plateau_max_evolution_steps=8)
    state = PlateauState(active=True, evolution_step=2, plateau_started_at=time.time())
    assert should_block_plateau_recovery(
        state,
        cfg=cfg,
        remediation_exhausted=False,
        trade_budget_remaining=40_000,
        stage_trades=9000,
        required=200,
    ) is False


@pytest.mark.unit
def test_hard_stop_blocks_only_after_ladder_exhausted() -> None:
    cfg = _cfg(plateau_trades_beyond_gate_multiplier=3)
    state = PlateauState(
        active=True,
        evolution_step=len(EVOLUTION_STEP_ACTIONS),
        plateau_started_at=time.time(),
    )
    assert evolution_ladder_exhausted(state) is True
    assert should_block_plateau_recovery(
        state,
        cfg=cfg,
        remediation_exhausted=True,
        trade_budget_remaining=40_000,
        stage_trades=9000,
        required=200,
    ) is True


@pytest.mark.unit
def test_terminal_not_instant_on_hard_stop_mid_ladder() -> None:
    cfg = _cfg(
        plateau_trades_beyond_gate_multiplier=3,
        beyond_gate_plateau_wall_sec=900,
        plateau_max_evolution_steps=8,
    )
    state = PlateauState(active=True, evolution_step=2, plateau_started_at=time.time())
    assert should_terminal_plateau_stall(
        state,
        stage_trades=9000,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="",
        remediation_exhausted=False,
        trade_budget_remaining=40_000,
    ) is False


@pytest.mark.unit
def test_terminal_after_ladder_exhausted_under_hard_stop() -> None:
    cfg = _cfg(plateau_trades_beyond_gate_multiplier=3)
    state = PlateauState(
        active=True,
        evolution_step=len(EVOLUTION_STEP_ACTIONS),
        plateau_started_at=time.time(),
    )
    assert should_terminal_plateau_stall(
        state,
        stage_trades=9000,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="",
        remediation_exhausted=False,
        trade_budget_remaining=40_000,
    ) is True


@pytest.mark.unit
def test_terminal_after_compressed_wall_under_hard_stop() -> None:
    cfg = _cfg(
        plateau_trades_beyond_gate_multiplier=3,
        beyond_gate_plateau_wall_sec=60,
    )
    state = PlateauState(
        active=True,
        evolution_step=2,
        plateau_started_at=time.time() - 120.0,
    )
    assert should_terminal_plateau_stall(
        state,
        stage_trades=9000,
        required=200,
        cfg=cfg,
        meta_self_eval_phase="",
        remediation_exhausted=False,
        trade_budget_remaining=40_000,
        now=time.time(),
    ) is True


@pytest.mark.unit
def test_compressed_ladder_force_advance_after_few_rollouts() -> None:
    cfg = _cfg(
        beyond_gate_evolution_rollouts_per_step=4,
        plateau_evolution_min_ppo_steps_between_steps=50_000,
        plateau_evolution_max_rollouts_per_step=24,
    )
    state = PlateauState(
        active=True,
        evolution_step=2,
        evolution_rollouts_this_step=8,
        plateau_started_at=time.time(),
        winrate_at_step_start=0.39,
    )
    assert should_force_advance_evolution_step(
        state,
        cfg=cfg,
        current_winrate=0.385,
        pass_target=0.45,
        ppo_steps_since_step_start=100,
        stage_trades=9000,
        required=200,
    ) is True
