"""Learning plateau detection and bounded evolution escalator (ADR-0023)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.plateau_escalator")

TERMINAL_STALL_REASON = "plateau_evolution_exhausted"


class EvolutionAction(str, Enum):
    DETECT = "detect"
    EXPAND_DATA = "expand_data"
    POLICY_ROLLBACK = "policy_rollback"
    INTRA_EASY_ONLY = "intra_easy_only"
    FRESH_POLICY = "fresh_policy_keep_buffer"
    ORACLE_DISTILL = "oracle_distill"
    PHOENIX_RESET = "phoenix_reset"
    TERMINAL = "terminal_stall"


EVOLUTION_STEP_ACTIONS: tuple[EvolutionAction, ...] = (
    EvolutionAction.EXPAND_DATA,
    EvolutionAction.POLICY_ROLLBACK,
    EvolutionAction.INTRA_EASY_ONLY,
    EvolutionAction.FRESH_POLICY,
    EvolutionAction.ORACLE_DISTILL,
    EvolutionAction.PHOENIX_RESET,
)

ACTION_LABELS: dict[EvolutionAction, str] = {
    EvolutionAction.DETECT: "Plateau detected",
    EvolutionAction.EXPAND_DATA: "Expand historical data window",
    EvolutionAction.POLICY_ROLLBACK: "Rollback policy to best winrate snapshot",
    EvolutionAction.INTRA_EASY_ONLY: "Intra-stage1 easy-only sampling",
    EvolutionAction.FRESH_POLICY: "Fresh policy init (keep buffer/oracle)",
    EvolutionAction.ORACLE_DISTILL: "Oracle distillation (top buffer trajectories)",
    EvolutionAction.PHOENIX_RESET: "Phoenix reset (fresh policy + oracle buffer)",
    EvolutionAction.TERMINAL: "Evolution exhausted — terminal stall",
}


@dataclass(slots=True)
class PlateauState:
    active: bool = False
    plateau_started_at: float = 0.0
    trades_at_plateau_start: int = 0
    best_winrate: float = 0.0
    best_winrate_at_trade: int = 0
    best_policy_path: str = ""
    evolution_step: int = 0
    evolution_rollouts_this_step: int = 0
    forced_recoveries_count: int = 0
    evolution_history: list[dict[str, Any]] = field(default_factory=list)
    winrate_at_step_start: float = 0.0
    full_recovery_cycles: int = 0

    def to_metrics(self) -> dict[str, Any]:
        return {
            "plateau_active": self.active,
            "plateau_started_at": float(self.plateau_started_at),
            "plateau_trades_at_start": int(self.trades_at_plateau_start),
            "plateau_best_winrate": round(float(self.best_winrate), 6),
            "plateau_best_winrate_at_trade": int(self.best_winrate_at_trade),
            "plateau_best_policy_path": str(self.best_policy_path or ""),
            "plateau_evolution_step": int(self.evolution_step),
            "plateau_evolution_rollouts_this_step": int(self.evolution_rollouts_this_step),
            "plateau_forced_recoveries_count": int(self.forced_recoveries_count),
            "plateau_evolution_history": list(self.evolution_history),
            "plateau_winrate_at_step_start": round(float(self.winrate_at_step_start), 6),
            "plateau_full_recovery_cycles": int(self.full_recovery_cycles),
        }

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any] | None) -> PlateauState:
        if not isinstance(metrics, dict):
            return cls()
        history = metrics.get("plateau_evolution_history")
        return cls(
            active=bool(metrics.get("plateau_active", False)),
            plateau_started_at=float(metrics.get("plateau_started_at", 0) or 0),
            trades_at_plateau_start=int(metrics.get("plateau_trades_at_start", 0) or 0),
            best_winrate=float(metrics.get("plateau_best_winrate", 0) or 0),
            best_winrate_at_trade=int(metrics.get("plateau_best_winrate_at_trade", 0) or 0),
            best_policy_path=str(metrics.get("plateau_best_policy_path", "") or ""),
            evolution_step=int(metrics.get("plateau_evolution_step", 0) or 0),
            evolution_rollouts_this_step=int(
                metrics.get("plateau_evolution_rollouts_this_step", 0) or 0
            ),
            forced_recoveries_count=int(metrics.get("plateau_forced_recoveries_count", 0) or 0),
            evolution_history=[dict(x) for x in history if isinstance(x, dict)]
            if isinstance(history, list)
            else [],
            winrate_at_step_start=float(metrics.get("plateau_winrate_at_step_start", 0) or 0),
            full_recovery_cycles=int(metrics.get("plateau_full_recovery_cycles", 0) or 0),
        )


def plateau_trades_beyond_gate(stage_trades: int, required: int) -> int:
    return max(0, int(stage_trades) - int(required))


def plateau_max_trades_beyond_gate(required: int, cfg: BirthCurriculumConfig) -> int:
    mult = max(1, int(cfg.plateau_trades_beyond_gate_multiplier))
    return int(required) * mult


@dataclass(slots=True)
class PlateauEnterContext:
    stage_trades: int
    stage_wins: int
    required: int
    winrate_trend_slope: float | None
    velocity_stall_attempts: int
    meta_self_eval_phase: str
    pass_metric_target: float = 0.45


def should_enter_plateau(ctx: PlateauEnterContext, *, cfg: BirthCurriculumConfig) -> bool:
    if not cfg.plateau_detection_enabled:
        return False
    if ctx.stage_trades < ctx.required:
        return False
    winrate = float(ctx.stage_wins) / float(max(1, ctx.stage_trades))
    gap = float(cfg.plateau_winrate_gap)
    if winrate >= float(ctx.pass_metric_target) - gap:
        return False
    slope = abs(float(ctx.winrate_trend_slope or 0.0))
    if slope >= float(cfg.velocity_stall_epsilon):
        return False
    exhausted = str(ctx.meta_self_eval_phase or "").strip().lower() == "exhausted"
    velocity_met = ctx.velocity_stall_attempts >= int(cfg.velocity_stall_attempt_threshold)
    beyond = plateau_trades_beyond_gate(ctx.stage_trades, ctx.required)
    beyond_met = beyond >= plateau_max_trades_beyond_gate(ctx.required, cfg)
    if not (exhausted or velocity_met or beyond_met):
        return False
    return True


def enter_plateau(
    state: PlateauState,
    *,
    stage_trades: int,
    stage_wins: int,
    now: float | None = None,
) -> None:
    ts = float(now if now is not None else time.time())
    winrate = float(stage_wins) / float(max(1, stage_trades))
    state.active = True
    state.plateau_started_at = ts
    state.trades_at_plateau_start = int(stage_trades)
    state.evolution_step = 0
    state.evolution_rollouts_this_step = 0
    state.winrate_at_step_start = winrate
    logger.warning(
        "birth.plateau.entered trades=%s winrate=%.2f%%",
        stage_trades,
        winrate * 100.0,
    )


def reset_plateau_for_new_cycle(state: PlateauState, *, stage_trades: int, stage_wins: int) -> None:
    """Restart evolution ladder after remediation cycle while keeping best snapshot."""
    state.active = True
    state.evolution_step = 0
    state.evolution_rollouts_this_step = 0
    state.forced_recoveries_count = 0
    state.winrate_at_step_start = float(stage_wins) / float(max(1, stage_trades))
    state.full_recovery_cycles += 1
    logger.warning(
        "birth.plateau.cycle_reset cycle=%s trades=%s winrate=%.2f%%",
        state.full_recovery_cycles,
        stage_trades,
        state.winrate_at_step_start * 100.0,
    )


def plateau_elapsed_sec(state: PlateauState, *, now: float | None = None) -> float:
    if not state.active or state.plateau_started_at <= 0:
        return 0.0
    return max(0.0, float(now if now is not None else time.time()) - state.plateau_started_at)


def remediation_is_exhausted(
    *,
    remediation_active: bool,
    remediation_step: int,
    remediation_cycle: int,
    cfg: BirthCurriculumConfig,
) -> bool:
    if not cfg.stall_remediation_enabled:
        return True
    if remediation_active:
        return False
    if remediation_cycle <= 0:
        return False
    return remediation_step >= int(cfg.stall_remediation_max_steps) and remediation_cycle >= int(
        cfg.stall_remediation_max_cycles
    )


def should_block_plateau_recovery(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    remediation_exhausted: bool,
    trade_budget_remaining: int,
) -> bool:
    """True when adaptive/never-stop recovery must stop (budget-gated never-stop)."""
    if not state.active or not cfg.plateau_detection_enabled:
        return False
    if state.evolution_step < int(cfg.plateau_max_evolution_steps):
        return False
    if cfg.stall_remediation_enabled and not remediation_exhausted:
        return False
    if int(trade_budget_remaining) > 0:
        return False
    return True


def should_terminal_plateau_stall(
    state: PlateauState,
    *,
    stage_trades: int,
    required: int,
    cfg: BirthCurriculumConfig,
    meta_self_eval_phase: str,
    remediation_exhausted: bool = True,
    trade_budget_remaining: int | None = None,
    now: float | None = None,
) -> bool:
    del stage_trades, required, meta_self_eval_phase
    if not state.active or not cfg.plateau_detection_enabled:
        return False
    if trade_budget_remaining is not None and int(trade_budget_remaining) <= 0:
        return True
    if state.evolution_step < int(cfg.plateau_max_evolution_steps):
        return False
    if cfg.stall_remediation_enabled and not remediation_exhausted:
        return False
    elapsed = plateau_elapsed_sec(state, now=now)
    if elapsed >= float(cfg.plateau_max_wall_sec):
        return True
    return remediation_exhausted


def can_force_never_stop_recovery(state: PlateauState, *, cfg: BirthCurriculumConfig) -> bool:
    if not state.active:
        return True
    return state.forced_recoveries_count < int(cfg.max_forced_recoveries_per_plateau)


def record_forced_recovery(state: PlateauState) -> None:
    state.forced_recoveries_count += 1


def should_start_evolution_step(state: PlateauState) -> bool:
    return state.active and state.evolution_step <= 0


def should_advance_evolution_step(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    current_winrate: float,
) -> bool:
    if not state.active or state.evolution_step <= 0:
        return False
    if state.evolution_rollouts_this_step < int(cfg.plateau_evolution_rollouts_per_step):
        return False
    if current_winrate > state.winrate_at_step_start + float(cfg.velocity_stall_epsilon):
        return False
    return True


def evolution_ladder_blocked_reason(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    current_winrate: float,
    remediation_exhausted: bool,
    trade_budget_remaining: int,
) -> str | None:
    if not state.active:
        return "plateau_inactive"
    if should_block_plateau_recovery(
        state,
        cfg=cfg,
        remediation_exhausted=remediation_exhausted,
        trade_budget_remaining=trade_budget_remaining,
    ):
        return "recovery_blocked_budget_or_exhausted"
    if state.evolution_step <= 0:
        return None
    if state.evolution_rollouts_this_step < int(cfg.plateau_evolution_rollouts_per_step):
        return f"awaiting_rollouts {state.evolution_rollouts_this_step}/{cfg.plateau_evolution_rollouts_per_step}"
    if current_winrate > state.winrate_at_step_start + float(cfg.velocity_stall_epsilon):
        return "winrate_improving"
    return None


def detect_hold_trap(
    *,
    hold_ratio: float,
    winrate: float,
    pass_metric_target: float,
    velocity_stall: bool,
    cfg: BirthCurriculumConfig,
) -> bool:
    if not velocity_stall:
        return False
    gap = float(getattr(cfg, "hold_trap_winrate_gap", 0.10))
    threshold = float(getattr(cfg, "hold_trap_hold_ratio_threshold", 0.55))
    return hold_ratio > threshold and winrate < float(pass_metric_target) - gap


def should_phoenix_reset(state: PlateauState, *, cfg: BirthCurriculumConfig, winrate: float) -> bool:
    min_cycles = int(getattr(cfg, "phoenix_reset_min_full_cycles", 3))
    max_wr = float(getattr(cfg, "phoenix_reset_max_winrate", 0.30))
    return state.full_recovery_cycles >= min_cycles and winrate < max_wr


def action_for_step(step: int) -> EvolutionAction:
    if step <= 0:
        return EvolutionAction.DETECT
    if step > len(EVOLUTION_STEP_ACTIONS):
        return EvolutionAction.TERMINAL
    return EVOLUTION_STEP_ACTIONS[step - 1]


def begin_evolution_step(
    state: PlateauState,
    *,
    stage_trades: int,
    stage_wins: int,
) -> EvolutionAction:
    state.evolution_step += 1
    state.evolution_rollouts_this_step = 0
    state.winrate_at_step_start = float(stage_wins) / float(max(1, stage_trades))
    action = action_for_step(state.evolution_step)
    logger.info(
        "birth.plateau.evolution_step step=%s action=%s winrate=%.2f%%",
        state.evolution_step,
        action.value,
        state.winrate_at_step_start * 100.0,
    )
    return action


def record_evolution_outcome(
    state: PlateauState,
    *,
    action: EvolutionAction,
    stage_trades: int,
    stage_wins: int,
    detail: str = "",
) -> None:
    winrate = float(stage_wins) / float(max(1, stage_trades))
    state.evolution_history.append(
        {
            "timestamp": time.time(),
            "step": int(state.evolution_step),
            "action": action.value,
            "winrate": round(winrate, 6),
            "trades": int(stage_trades),
            "detail": str(detail or ""),
        }
    )


def maybe_update_best_winrate(
    state: PlateauState,
    *,
    stage_trades: int,
    stage_wins: int,
    policy_path: str,
    cfg: BirthCurriculumConfig,
) -> bool:
    if not cfg.plateau_save_best_policy:
        return False
    winrate = float(stage_wins) / float(max(1, stage_trades))
    if stage_trades < 1 or winrate <= state.best_winrate:
        return False
    state.best_winrate = winrate
    state.best_winrate_at_trade = int(stage_trades)
    if policy_path:
        state.best_policy_path = str(policy_path)
    return True


def increment_evolution_rollout(state: PlateauState) -> None:
    if state.active:
        state.evolution_rollouts_this_step += 1


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
    action = action_for_step(state.evolution_step) if state.evolution_step > 0 else EvolutionAction.DETECT
    if state.evolution_step <= 0:
        phase = "detected"
    elif state.evolution_step >= int(cfg.plateau_max_evolution_steps):
        phase = "exhausted"
    else:
        phase = f"step_{state.evolution_step}"
    remaining = max(0, int(cfg.plateau_max_evolution_steps) - int(state.evolution_step))
    label = ACTION_LABELS.get(action, action.value)
    if state.evolution_step > 0 and state.best_winrate > 0:
        label = f"{label} (best winrate {state.best_winrate:.1%})"
    return {
        "evolution_phase": phase,
        "evolution_step": int(state.evolution_step),
        "evolution_step_label": label,
        "evolution_actions_remaining": remaining,
        "plateau_elapsed_sec": round(plateau_elapsed_sec(state, now=now), 2),
        "trades_beyond_gate": plateau_trades_beyond_gate(stage_trades, required),
        "plateau_forced_recoveries_count": int(state.forced_recoveries_count),
        "plateau_best_winrate": round(float(state.best_winrate), 6),
        "plateau_full_recovery_cycles": int(state.full_recovery_cycles),
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
    )
    hold_trap = detect_hold_trap(
        hold_ratio=hold_ratio,
        winrate=winrate,
        pass_metric_target=pass_target,
        velocity_stall=velocity_stall,
        cfg=cfg,
    )
    recommended = "continue_evolution"
    if hold_trap:
        recommended = "explore_boost_anti_hold"
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
        "evolution_ladder_blocked_reason": blocked,
        "recommended_recovery_action": recommended,
        "terminal_plateau_recommended": terminal,
        "terminal_stall_reason": TERMINAL_STALL_REASON if terminal else None,
    }
