"""Plateau progress / quarantine / audit telemetry payloads."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_enter import (
    is_plateau_quarantine_blocking,
    plateau_max_trades_beyond_gate,
    plateau_trades_beyond_gate,
)
from lumina_core.birth.plateau_evolution_ladder import (
    ACTION_LABELS,
    EVOLUTION_STEP_ACTIONS,
    EvolutionAction,
    action_for_step,
    evolution_actions_completed,
    evolution_phantom_steps,
)
from lumina_core.birth.plateau_terminal import (
    TERMINAL_STALL_REASON,
    detect_hold_trap,
    detect_over_trading_trap,
    detect_under_activity_trap,
    evolution_ladder_blocked_reason,
    plateau_elapsed_sec,
    should_phoenix_reset,
    should_terminal_plateau_stall,
)

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState


def quarantine_trades_remaining(
    quarantine: dict[str, Any],
    *,
    stage_trades: int,
) -> int:
    """New trades still required before quarantine ends."""
    if not quarantine.get("plateau_quarantine_active"):
        return 0
    trades_at = int(quarantine.get("plateau_quarantine_trades_at_resume", 0) or 0)
    min_new = int(quarantine.get("plateau_quarantine_trades_remaining", 0) or 0)
    new_trades = max(0, int(stage_trades) - trades_at)
    return max(0, min_new - new_trades)


def quarantine_progress_payload(
    quarantine: dict[str, Any],
    *,
    stage_trades: int,
    cfg: BirthCurriculumConfig,
) -> dict[str, Any]:
    """Progress fields for quarantine UI (computed remaining trades)."""
    payload = dict(quarantine)
    if not quarantine.get("plateau_quarantine_active"):
        payload["plateau_quarantine_trades_new"] = 0
        payload["plateau_quarantine_trades_remaining_count"] = 0
        payload["plateau_quarantine_blocking"] = False
        return payload
    trades_at = int(quarantine.get("plateau_quarantine_trades_at_resume", 0) or 0)
    min_new = int(
        quarantine.get("plateau_quarantine_trades_remaining", cfg.plateau_quarantine_min_trades)
        or cfg.plateau_quarantine_min_trades
    )
    new_trades = max(0, int(stage_trades) - trades_at)
    payload["plateau_quarantine_trades_new"] = new_trades
    payload["plateau_quarantine_trades_remaining_count"] = max(0, min_new - new_trades)
    payload["plateau_quarantine_blocking"] = is_plateau_quarantine_blocking(
        quarantine_rollouts_remaining=int(
            quarantine.get("plateau_quarantine_rollouts_remaining", 0) or 0
        ),
        quarantine_trades_at_resume=trades_at,
        stage_trades=int(stage_trades),
        quarantine_min_trades=min_new,
    )
    return payload

def progress_fields(
    state: PlateauState,
    *,
    stage_trades: int,
    required: int,
    cfg: BirthCurriculumConfig,
    now: float | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    step_cap = max(
        1,
        int(
            max_steps
            if max_steps is not None
            else getattr(cfg, "plateau_max_evolution_steps", 8) or 8
        ),
    )
    if not state.active:
        return {
            "evolution_phase": "none",
            "evolution_step": 0,
            "evolution_step_label": "",
            "evolution_actions_remaining": step_cap,
            "plateau_elapsed_sec": 0.0,
            "trades_beyond_gate": plateau_trades_beyond_gate(stage_trades, required),
            "plateau_forced_recoveries_count": 0,
        }
    # progress_fields is stage-agnostic; labels may lag stage3 remap until caller passes stage.
    action = (
        action_for_step(state.evolution_step)
        if state.evolution_step > 0
        else EvolutionAction.DETECT
    )
    if state.evolution_step <= 0:
        phase = "detected"
    elif state.evolution_step >= step_cap:
        phase = "exhausted"
    else:
        phase = f"step_{state.evolution_step}"
    actions_total = min(len(EVOLUTION_STEP_ACTIONS), step_cap)
    actions_completed = evolution_actions_completed(state, max_steps=step_cap)
    phantom_steps = evolution_phantom_steps(state, max_steps=step_cap)
    remaining = max(0, actions_total - actions_completed)
    max_rollouts = int(getattr(cfg, "plateau_evolution_max_rollouts_per_step", 24))
    label = ACTION_LABELS.get(action, action.value)
    if state.evolution_step > 0 and state.best_winrate > 0:
        label = f"{label} (best winrate {state.best_winrate:.1%})"
    return {
        "evolution_phase": phase,
        "evolution_step": int(state.evolution_step),
        "evolution_step_label": label,
        "evolution_actions_total": actions_total,
        "evolution_actions_completed": actions_completed,
        "evolution_phantom_steps": phantom_steps,
        "evolution_actions_remaining": remaining,
        "plateau_elapsed_sec": round(plateau_elapsed_sec(state, now=now), 2),
        "trades_beyond_gate": plateau_trades_beyond_gate(stage_trades, required),
        "plateau_forced_recoveries_count": int(state.forced_recoveries_count),
        "plateau_best_winrate": round(float(state.best_winrate), 6),
        "plateau_best_winrate_at_cycle_start": round(
            float(state.best_winrate_at_cycle_start), 6
        ),
        "plateau_full_recovery_cycles": int(state.full_recovery_cycles),
        "plateau_evolution_rollouts_this_step": int(state.evolution_rollouts_this_step),
        "plateau_evolution_rollouts_per_step": int(cfg.plateau_evolution_rollouts_per_step),
        "plateau_evolution_rollouts_max": max_rollouts,
        "plateau_evolution_max_steps_effective": step_cap,
    }


def build_plateau_audit(
    state: PlateauState,
    *,
    stage_trades: int,
    required: int,
    cfg: BirthCurriculumConfig,
    progress: dict[str, Any],
    remediation_exhausted: bool = True,
    trade_budget_remaining: int | None = None,
    max_steps: int | None = None,
) -> dict[str, Any]:
    winrate = float(progress.get("stage_winrate", 0) or 0)
    if not winrate and progress.get("stage_wins") is not None and stage_trades:
        winrate = int(progress.get("stage_wins", 0) or 0) / max(1, stage_trades)
    hold_ratio = float(progress.get("stage_hold_ratio", 0) or 0)
    raw_target = progress.get("pass_metric_target")
    pass_target: float
    try:
        if raw_target is None:
            raise TypeError("foundation metric has no WR pass target")
        pass_target = float(raw_target)
        if pass_target <= 0.0:
            raise ValueError("non-positive pass_metric_target")
    except (TypeError, ValueError):
        # S1 Closed loop: metric_target is null (median loss R max). Never invent 45%.
        try:
            pass_target = float(
                progress.get("stage1_foundation_target_wr")
                or progress.get("birth_survival_wr_floor")
                or 0.20
            )
        except (TypeError, ValueError):
            pass_target = 0.20
    velocity_stall = int(progress.get("velocity_stall_attempts", 0) or 0) >= int(
        cfg.velocity_stall_attempt_threshold
    )
    budget_remaining = trade_budget_remaining
    if budget_remaining is None:
        budget_remaining = int(progress.get("trade_budget_remaining", 0) or 0)
    # Prefer caller max_steps; fall back to progress effective cap (certified SSOT).
    step_cap = max_steps
    if step_cap is None:
        raw_cap = progress.get("plateau_evolution_max_steps_effective")
        if raw_cap is not None:
            try:
                step_cap = int(raw_cap)
            except (TypeError, ValueError):
                step_cap = None
    terminal = should_terminal_plateau_stall(
        state,
        stage_trades=stage_trades,
        required=required,
        cfg=cfg,
        meta_self_eval_phase=str(progress.get("meta_self_eval_phase", "") or ""),
        remediation_exhausted=remediation_exhausted,
        trade_budget_remaining=budget_remaining,
        max_steps=step_cap,
    )
    blocked = evolution_ladder_blocked_reason(
        state,
        cfg=cfg,
        current_winrate=winrate,
        remediation_exhausted=remediation_exhausted,
        trade_budget_remaining=int(budget_remaining),
        stage_trades=stage_trades,
        required=required,
        pass_target=pass_target,
        max_steps=step_cap,
    )
    raw_flat = progress.get("stage_range_flat_ratio")
    try:
        hold_flat = float(raw_flat) if raw_flat is not None else None
    except (TypeError, ValueError):
        hold_flat = None
    hold_trap = detect_hold_trap(
        hold_ratio=hold_ratio,
        winrate=winrate,
        pass_metric_target=pass_target,
        velocity_stall=velocity_stall,
        cfg=cfg,
        range_flat_ratio=hold_flat,
    )
    range_flat_ratio = float(progress.get("stage_range_flat_ratio", 0) or 0)
    try:
        occ_ctrl = progress.get("occupancy_control_flat")
        occ_ctrl_f = float(occ_ctrl) if occ_ctrl is not None else None
    except (TypeError, ValueError):
        occ_ctrl_f = None
    # Envelope geometry (FORCE_HOLD at ~30% flat) is not a policy freeze trap.
    last_mode = str(progress.get("participation_last_mode") or "").strip().upper()
    occupancy_geometry = 0.25 <= range_flat_ratio <= 0.75
    if occ_ctrl_f is not None and 0.25 <= occ_ctrl_f <= 0.75:
        occupancy_geometry = True
    if bool(progress.get("pass_vector_in_flat_band")):
        occupancy_geometry = True
    if occupancy_geometry or last_mode in {"FORCE_HOLD", "FORCE_FLAT", "FORCE_EXIT"}:
        hold_trap = False
    range_round_trips = int(progress.get("stage_range_round_trips", 0) or 0)
    range_total_signals = int(
        progress.get("stage_range_total_signals", 0)
        or progress.get("range_total_signals", 0)
        or 0
    )
    over_trading = detect_over_trading_trap(
        range_flat_ratio=range_flat_ratio,
        range_round_trips=range_round_trips,
        required=required,
        velocity_stall=velocity_stall,
        cfg=cfg,
    )
    under_activity = detect_under_activity_trap(
        range_flat_ratio=range_flat_ratio,
        range_total_signals=range_total_signals,
        stage_trades=stage_trades,
        required=required,
        velocity_stall=velocity_stall,
        cfg=cfg,
    )
    # Fallback: blocker metric from progress when range counters absent.
    if not under_activity and not over_trading:
        blocker = str(progress.get("stage_blocker_metric", "") or "").strip().lower()
        blocker_val = float(progress.get("stage_blocker_value", 0) or 0)
        if blocker == "position_flat" and blocker_val > float(
            getattr(cfg, "under_activity_flat_threshold", 0.70) or 0.70
        ):
            under_activity = True
    from lumina_core.birth.expectancy_stall import (
        detect_expectancy_stall,
        recommended_expectancy_recovery_action,
    )

    roll_wr = progress.get("rolling_winrate_500")
    try:
        roll_wr_f = float(roll_wr) if roll_wr is not None else None
    except (TypeError, ValueError):
        roll_wr_f = None
    beyond = plateau_trades_beyond_gate(stage_trades, required)
    stage_key = str(
        progress.get("curriculum_stage") or progress.get("stage_display_name") or ""
    ).lower()
    stage_is_range = "stage2" in stage_key or (
        "range" in stage_key and "mixed" not in stage_key
    )
    stage_is_mixed = "stage3" in stage_key or "mixed" in stage_key
    expectancy_stall = detect_expectancy_stall(
        stage_is_range=stage_is_range,
        stage_is_mixed=stage_is_mixed,
        range_flat_ratio=range_flat_ratio,
        range_total_signals=range_total_signals,
        stage_trades=stage_trades,
        stage_wins=int(progress.get("stage_wins", 0) or round(winrate * max(1, stage_trades))),
        required=required,
        velocity_stall=velocity_stall,
        plateau_active=bool(state.active),
        trades_beyond_gate=beyond,
        rolling_winrate=roll_wr_f,
        cfg=cfg,
    )
    # Only treat expectancy stall when not in dual occupancy traps.
    if under_activity or over_trading:
        expectancy_stall = False
    # Blocker metric override for stage2 range quality.
    if not expectancy_stall:
        blocker = str(progress.get("stage_blocker_metric", "") or "").strip().lower()
        if blocker == "expectancy":
            expectancy_stall = True
    recommended = "continue_evolution"
    if under_activity:
        # Stage2 chronic flat: participation pressure before rollback/swarm theater.
        recommended = "explore_boost_anti_flat"
    elif hold_trap and not expectancy_stall:
        recommended = "explore_boost_anti_hold"
    elif over_trading:
        recommended = "range_patience_recovery"
    elif expectancy_stall:
        rem_step = int(progress.get("expectancy_quality_step", 0) or 0)
        recommended = recommended_expectancy_recovery_action(
            range_flat_ratio=range_flat_ratio,
            remediation_step=rem_step,
        )
    elif state.best_policy_path:
        recommended = "policy_rollback"
    if should_phoenix_reset(state, cfg=cfg, winrate=winrate):
        recommended = "phoenix_reset"
    return {
        "plateau_active": state.active,
        "plateau_elapsed_sec": plateau_elapsed_sec(state),
        "evolution_step": state.evolution_step,
        "evolution_history": list(state.evolution_history),
        "best_winrate": state.best_winrate,
        "best_winrate_at_trade": state.best_winrate_at_trade,
        "best_policy_path": state.best_policy_path,
        "trades_beyond_gate": beyond,
        "trades_beyond_gate_max": plateau_max_trades_beyond_gate(required, cfg),
        "forced_recoveries_count": state.forced_recoveries_count,
        "forced_recoveries_max": int(cfg.max_forced_recoveries_per_plateau),
        "full_recovery_cycles": state.full_recovery_cycles,
        "live_winrate": round(winrate, 6),
        "hold_trap_detected": hold_trap,
        "over_trading_detected": over_trading,
        "under_activity_detected": under_activity,
        "expectancy_stall_detected": expectancy_stall,
        "evolution_ladder_blocked_reason": blocked,
        "recommended_recovery_action": recommended,
        "terminal_plateau_recommended": terminal,
        "terminal_stall_reason": TERMINAL_STALL_REASON if terminal else None,
    }
