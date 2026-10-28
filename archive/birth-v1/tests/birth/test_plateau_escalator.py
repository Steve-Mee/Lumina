"""Plateau evolution escalator (ADR-0023) + never-stop fixes."""

from __future__ import annotations

import time

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    PlateauState,
    action_for_step,
    build_plateau_audit,
    can_force_never_stop_recovery,
    detect_hold_trap,
    enter_plateau,
    evolution_ladder_blocked_reason,
    maybe_update_best_winrate,
    reset_plateau_for_new_cycle,
    sanitize_stuck_plateau_evolution,
    should_advance_evolution_step,
    should_block_phoenix_no_lift,
    should_block_plateau_recovery,
    should_brake_recovery_no_lift,
    should_force_advance_evolution_step,
    should_start_evolution_step,
    should_terminal_plateau_stall,
    should_trigger_plateau_evolution_step,
    revert_evolution_step_on_noop,
    rolling_winrate_last_n_trades,
    winrate_improvement_blocks_ladder,
)
from lumina_core.birth.stall_remediation import curate_buffer_top_quartile


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = dict(
        plateau_detection_enabled=True,
        plateau_winrate_gap=0.10,
        plateau_trades_beyond_gate_multiplier=3,
        plateau_max_wall_sec=7200,
        plateau_max_evolution_steps=8,
        plateau_evolution_rollouts_per_step=12,
        max_forced_recoveries_per_plateau=12,
        velocity_stall_attempt_threshold=32,
        velocity_stall_epsilon=0.002,
        stall_remediation_enabled=True,
        stall_remediation_max_cycles=3,
        stall_remediation_max_steps=5,
        plateau_evolution_min_ppo_steps_between_steps=0,
    )
    base.update(overrides)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_meta_exhausted_beyond_gate_does_not_terminal_before_evolution() -> None:
    cfg = _cfg(plateau_max_evolution_steps=8, plateau_trades_beyond_gate_multiplier=10)
    state = PlateauState(active=True, evolution_step=0, plateau_started_at=time.time() - 9000)
    assert should_terminal_plateau_stall(
        state,
        stage_trades=500,
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
def test_detect_hold_trap_stage3_learning_target_not_zero() -> None:
    """Stage 3 pass floor is WR>=35%; hold-trap still uses recommended learning WR."""
    from lumina_core.birth.curriculum import CurriculumStage
    from lumina_core.birth.stage_scorecard import learning_metric_target, pass_criteria_for_stage

    cfg = _cfg()
    criteria = pass_criteria_for_stage(CurriculumStage.STAGE3_MIXED, cfg=cfg)
    learning_target = learning_metric_target(
        CurriculumStage.STAGE3_MIXED,
        cfg=cfg,
        pass_criteria=criteria,
    )
    # EdgeScore stage-3 criteria use metric_target=None; hygiene floor stays in config/label.
    wr_floor = float(getattr(cfg, "stage3_winrate_floor", 0.35))
    if bool(getattr(cfg, "stage3_edgescore_enabled", True)):
        assert criteria.metric_target is None
        assert criteria.id in {"mixed_regimes", "mixed_edgescore"}
    else:
        assert criteria.metric_target == pytest.approx(wr_floor)
    assert learning_target == pytest.approx(0.45)
    assert detect_hold_trap(
        hold_ratio=0.80,
        winrate=0.34,
        pass_metric_target=learning_target,
        velocity_stall=True,
        cfg=cfg,
        range_flat_ratio=0.90,
    )
    assert not detect_hold_trap(
        hold_ratio=0.80,
        winrate=0.34,
        pass_metric_target=learning_target,
        velocity_stall=True,
        cfg=cfg,
        range_flat_ratio=0.32,
    )
    # Pass-floor target (0.35) with gap 0.10 needs wr < 0.25 — 0.34 does not trip.
    assert not detect_hold_trap(
        hold_ratio=0.80,
        winrate=0.34,
        pass_metric_target=wr_floor,
        velocity_stall=True,
        cfg=cfg,
    )


@pytest.mark.unit
def test_occupancy_pin_does_not_recommend_explore_boost_anti_hold() -> None:
    """PID 19776: 93% HOLD at flat 0.2996 is envelope geometry, not a freeze trap."""
    cfg = _cfg()
    state = PlateauState(active=True)
    audit = build_plateau_audit(
        state,
        stage_trades=1168,
        required=300,
        cfg=cfg,
        progress={
            "curriculum_stage": "stage2_range",
            "stage_winrate": 0.3112,
            "stage_hold_ratio": 0.933,
            "pass_metric_target": 0.45,
            "velocity_stall_attempts": 66,
            "stage_range_flat_ratio": 0.2996,
            "occupancy_control_flat": 0.2996,
            "participation_last_mode": "FORCE_HOLD",
            "stage_range_round_trips": 1168,
            "stage_range_total_signals": 35193,
            "stage_blocker_metric": "expectancy",
            "stage_blocker_value": -0.185,
            "rolling_winrate_500": 0.301667,
            "expectancy_quality_step": 4,
        },
    )
    assert audit["hold_trap_detected"] is False
    assert audit["recommended_recovery_action"] != "explore_boost_anti_hold"


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
    ) is True


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
def test_force_advance_blocked_when_winrate_meaningfully_improving() -> None:
    cfg = _cfg(
        plateau_evolution_max_rollouts_per_step=24,
        stage1_winrate_pass_threshold=0.35,
        stage1_winrate_pass_floor=0.35,
    )
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=24,
        winrate_at_step_start=0.268,
    )
    assert should_force_advance_evolution_step(
        state, cfg=cfg, current_winrate=0.30, pass_target=0.35
    ) is False


@pytest.mark.unit
def test_micro_improvement_does_not_block_ladder() -> None:
    cfg = _cfg(
        plateau_evolution_max_rollouts_per_step=24,
        stage1_winrate_pass_threshold=0.35,
        stage1_winrate_pass_floor=0.35,
    )
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=24,
        winrate_at_step_start=0.227,
    )
    assert winrate_improvement_blocks_ladder(
        state, current_winrate=0.246, cfg=cfg, pass_target=0.35
    ) is False
    assert should_force_advance_evolution_step(
        state, cfg=cfg, current_winrate=0.246, pass_target=0.35
    ) is True


@pytest.mark.unit
def test_safety_valve_forces_advance_after_triple_max_rollouts() -> None:
    cfg = _cfg(
        plateau_evolution_max_rollouts_per_step=24,
        stage1_winrate_pass_threshold=0.35,
        stage1_winrate_pass_floor=0.35,
    )
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=496,
        winrate_at_step_start=0.227,
    )
    assert should_force_advance_evolution_step(
        state, cfg=cfg, current_winrate=0.246, pass_target=0.35
    ) is True


@pytest.mark.unit
def test_sanitize_stuck_plateau_evolution_caps_rollouts() -> None:
    cfg = _cfg(plateau_evolution_max_rollouts_per_step=24)
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=496,
        winrate_at_step_start=0.227,
    )
    assert sanitize_stuck_plateau_evolution(
        state, cfg=cfg, current_winrate=0.246, pass_target=0.35
    ) is True
    assert state.evolution_rollouts_this_step >= 72


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


@pytest.mark.unit
def test_revert_evolution_step_on_noop_undoes_ladder() -> None:
    state = PlateauState(active=True, evolution_step=3, evolution_rollouts_this_step=8)
    revert_evolution_step_on_noop(state)
    assert state.evolution_step == 2
    assert state.evolution_rollouts_this_step == 0


@pytest.mark.unit
def test_force_advance_after_max_noops() -> None:
    cfg = _cfg(plateau_evolution_max_noops_per_step=3)
    state = PlateauState(active=True, evolution_step=1, evolution_noop_count=3)
    assert should_force_advance_evolution_step(state, cfg=cfg, current_winrate=0.28) is True


@pytest.mark.unit
def test_min_ppo_steps_blocks_advance() -> None:
    cfg = _cfg(
        plateau_evolution_rollouts_per_step=12,
        plateau_evolution_min_ppo_steps_between_steps=50_000,
    )
    state = PlateauState(
        active=True,
        evolution_step=1,
        evolution_rollouts_this_step=12,
        winrate_at_step_start=0.268,
    )
    assert should_advance_evolution_step(
        state,
        cfg=cfg,
        current_winrate=0.268,
        ppo_steps_since_step_start=1000,
    ) is False
    assert should_advance_evolution_step(
        state,
        cfg=cfg,
        current_winrate=0.268,
        ppo_steps_since_step_start=50_000,
    ) is True


@pytest.mark.unit
def test_rolling_winrate_last_n_trades() -> None:
    wins_at = {0: 0, 100: 0, 600: 200}
    wr = rolling_winrate_last_n_trades(
        stage_trades=600,
        stage_wins=200,
        wins_at_trade=wins_at,
        window=500,
    )
    assert wr == pytest.approx(0.4, rel=1e-4)


@pytest.mark.unit
def test_evolution_ladder_blocked_reason_accepts_stage_trades() -> None:
    cfg = _cfg()
    state = PlateauState(active=True, evolution_step=1, evolution_rollouts_this_step=0)
    blocked = evolution_ladder_blocked_reason(
        state,
        cfg=cfg,
        current_winrate=0.30,
        remediation_exhausted=True,
        trade_budget_remaining=40_000,
        stage_trades=847,
        required=200,
    )
    assert blocked is not None
    audit = build_plateau_audit(
        state,
        stage_trades=847,
        required=200,
        cfg=cfg,
        progress={"stage_winrate": 0.30, "stage_hold_ratio": 0.76},
    )
    assert "evolution_ladder_blocked_reason" in audit


@pytest.mark.unit
def test_no_lift_brake_after_full_ladder_without_best_improvement() -> None:
    state = PlateauState(
        active=True,
        best_winrate=0.435,
        best_winrate_at_cycle_start=0.435,
        evolution_step=6,
        full_recovery_cycles=0,
    )
    assert should_brake_recovery_no_lift(state) is True
    assert should_block_phoenix_no_lift(state) is True
    assert should_terminal_plateau_stall(
        state,
        stage_trades=2700,
        required=200,
        cfg=_cfg(),
        meta_self_eval_phase="probing",
        remediation_exhausted=False,
        trade_budget_remaining=40_000,
    ) is True


@pytest.mark.unit
def test_no_lift_brake_false_when_best_improved() -> None:
    state = PlateauState(
        active=True,
        best_winrate=0.46,
        best_winrate_at_cycle_start=0.435,
        evolution_step=6,
        full_recovery_cycles=0,
    )
    assert should_brake_recovery_no_lift(state) is False
    assert should_block_phoenix_no_lift(state) is False


@pytest.mark.unit
def test_cycle_reset_increments_and_snapshots_best_at_cycle_start() -> None:
    state = PlateauState(active=True, best_winrate=0.435, evolution_step=6)
    enter_plateau(state, stage_trades=800, stage_wins=280)
    assert state.best_winrate_at_cycle_start == pytest.approx(0.435)
    assert state.evolution_step == 0
    state.evolution_step = 6
    reset_plateau_for_new_cycle(state, stage_trades=1700, stage_wins=590)
    assert state.full_recovery_cycles == 1
    assert state.best_winrate_at_cycle_start == pytest.approx(0.435)
    assert state.evolution_step == 0


@pytest.mark.unit
def test_block_phoenix_after_completed_cycle_without_lift() -> None:
    state = PlateauState(
        active=True,
        best_winrate=0.40,
        best_winrate_at_cycle_start=0.435,
        evolution_step=3,
        full_recovery_cycles=1,
    )
    assert should_brake_recovery_no_lift(state) is False  # ladder not exhausted
    assert should_block_phoenix_no_lift(state) is True

