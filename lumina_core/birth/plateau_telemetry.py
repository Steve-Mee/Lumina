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
) -> dict[str, Any]:
    if not state.active:
        return {
            "evolution_phase": "none",
            "evolution_step": 0,
            "evolution_step_label": "",
            "evolution_actions_remaining": int(cfg.plateau_max_evolution_steps),
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
    elif state.evolution_step >= int(cfg.plateau_max_evolution_steps):
        phase = "exhausted"
    else:
        phase = f"step_{state.evolution_step}"
    actions_total = len(EVOLUTION_STEP_ACTIONS)
    actions_completed = evolution_actions_completed(state)
    phantom_steps = evolution_phantom_steps(state)
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
) -> dict[str, Any]:
    winrate = float(progress.get("stage_winrate", 0) or 0)
    if not winrate and progress.get("stage_wins") is not None and stage_trades:
        winrate = int(progress.get("stage_wins", 0) or 0) / max(1, stage_trades)
    hold_ratio = float(progress.get("stage_hold_ratio", 0) or 0)
    pass_target = float(progress.get("pass_metric_target", 0.45) or 0.45)
    velocity_stall = int(progress.get("velocity_stall_attempts", 0) or 0) >= int(
        cfg.velocity_stall_attempt_threshold
    )
    budget_remaining = trade_budget_remaining
    if budget_remaining is None:
        budget_remaining = int(progress.get("trade_budget_remaining", 0) or 0)
    terminal = should_terminal_plateau_stall(
        state,
        stage_trades=stage_trades,
        required=required,
        cfg=cfg,
        meta_self_eval_phase=str(progress.get("meta_self_eval_phase", "") or ""),
        remediation_exhausted=remediation_exhausted,
        trade_budget_remaining=budget_remaining,
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
    )
    hold_trap = detect_hold_trap(
        hold_ratio=hold_ratio,
        winrate=winrate,
        pass_metric_target=pass_target,
        velocity_stall=velocity_stall,
        cfg=cfg,
    )
    range_flat_ratio = float(progress.get("stage_range_flat_ratio", 0) or 0)
    range_round_trips = int(progress.get("stage_range_round_trips", 0) or 0)
    over_trading = detect_over_trading_trap(
        range_flat_ratio=range_flat_ratio,
        range_round_trips=range_round_trips,
        required=required,
        velocity_stall=velocity_stall,
        cfg=cfg,
    )
    recommended = "continue_evolution"
    if hold_trap:
        recommended = "explore_boost_anti_hold"
    elif over_trading:
        recommended = "range_patience_recovery"
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
        "trades_beyond_gate": plateau_trades_beyond_gate(stage_trades, required),
        "trades_beyond_gate_max": plateau_max_trades_beyond_gate(required, cfg),
        "forced_recoveries_count": state.forced_recoveries_count,
        "forced_recoveries_max": int(cfg.max_forced_recoveries_per_plateau),
        "full_recovery_cycles": state.full_recovery_cycles,
        "live_winrate": round(winrate, 6),
        "hold_trap_detected": hold_trap,
        "over_trading_detected": over_trading,
        "evolution_ladder_blocked_reason": blocked,
        "recommended_recovery_action": recommended,
        "terminal_plateau_recommended": terminal,
        "terminal_stall_reason": TERMINAL_STALL_REASON if terminal else None,
    }
