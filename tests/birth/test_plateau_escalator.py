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
    maybe_update_best_winrate,
    should_advance_evolution_step,
    should_block_plateau_recovery,
    should_force_advance_evolution_step,
    should_start_evolution_step,
    should_terminal_plateau_stall,
    should_trigger_plateau_evolution_step,
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


@pytest.mark.unit
def test_force_advance_after_max_rollouts_without_lift() -> None:
    cfg = _cfg(
        plateau_evolution_rollouts_per_step=12,
        plateau_evolution_max_rollouts_per_step=24,
    )
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=24,
        winrate_at_step_start=0.268,
    )
    assert should_force_advance_evolution_step(state, cfg=cfg, current_winrate=0.268) is True
    assert should_advance_evolution_step(state, cfg=cfg, current_winrate=0.268) is True
    assert should_trigger_plateau_evolution_step(state, cfg=cfg, current_winrate=0.268) is True


@pytest.mark.unit
def test_force_advance_blocked_when_winrate_improving() -> None:
    cfg = _cfg(plateau_evolution_max_rollouts_per_step=24)
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=24,
        winrate_at_step_start=0.268,
    )
    assert should_force_advance_evolution_step(state, cfg=cfg, current_winrate=0.30) is False


@pytest.mark.unit
def test_maybe_update_best_winrate_requires_min_trades() -> None:
    cfg = _cfg(plateau_best_policy_min_trades=200, plateau_save_best_policy=True)
    state = PlateauState(active=True, best_winrate=0.40)
    assert (
        maybe_update_best_winrate(
            state,
            stage_trades=42,
            stage_wins=20,
            policy_path="/tmp/best.zip",
            cfg=cfg,
        )
        is False
    )
    assert (
        maybe_update_best_winrate(
            state,
            stage_trades=250,
            stage_wins=120,
            policy_path="/tmp/best.zip",
            cfg=cfg,
        )
        is True
    )
    assert state.best_winrate == pytest.approx(0.48)


@pytest.mark.unit
def test_sanitize_plateau_best_snapshot_clears_early_spike() -> None:
    from lumina_core.birth.plateau_escalator import sanitize_plateau_best_snapshot

    cfg = _cfg(plateau_best_policy_min_trades=200)
    state = PlateauState(
        active=True,
        best_winrate=0.476,
        best_winrate_at_trade=42,
        best_policy_path="/tmp/spike.zip",
    )
    sanitize_plateau_best_snapshot(
        state,
        cfg=cfg,
        stage_trades=6113,
        stage_wins=1638,
    )
    assert state.best_winrate_at_trade >= 200
    assert state.best_winrate == pytest.approx(1638 / 6113, rel=1e-4)
    assert state.best_policy_path == ""


@pytest.mark.unit
def test_is_valid_best_policy_snapshot() -> None:
    from lumina_core.birth.plateau_escalator import is_valid_best_policy_snapshot

    cfg = _cfg(plateau_best_policy_min_trades=200)
    assert not is_valid_best_policy_snapshot(
        PlateauState(best_winrate=0.47, best_winrate_at_trade=42, best_policy_path="/x.zip"),
        cfg=cfg,
    )
    assert is_valid_best_policy_snapshot(
        PlateauState(best_winrate=0.47, best_winrate_at_trade=250, best_policy_path="/x.zip"),
        cfg=cfg,
    )
