"""Plateau evolution ladder advance, sanitize, and outcome helpers."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import stage1_winrate_pass_threshold
from lumina_core.birth.plateau_enter import should_trades_beyond_gate_hard_stop
from lumina_core.birth.plateau_evolution_ladder import (
    EVOLUTION_STEP_ACTIONS,
    EvolutionAction,
    evolution_ladder_exhausted,
)
from lumina_core.birth.plateau_terminal_traps import should_block_plateau_recovery
from lumina_core.logging_utils import get_logger

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState

logger = get_logger("lumina.birth.plateau_terminal")

_PLATEAU_GAP_PROGRESS_MIN = 0.25


def revert_evolution_step_on_noop(state: PlateauState) -> None:
    """Undo ladder advance when an evolution action did not apply."""
    if state.evolution_step > 0:
        state.evolution_step -= 1
    state.evolution_rollouts_this_step = 0

def should_start_evolution_step(state: PlateauState) -> bool:
    return state.active and state.evolution_step <= 0


def winrate_improvement_blocks_ladder(
    state: PlateauState,
    *,
    current_winrate: float,
    cfg: BirthCurriculumConfig,
    pass_target: float,
) -> bool:
    """True when winrate lift is meaningful enough to defer the next evolution step."""
    if state.evolution_step <= 0:
        return False
    delta = float(current_winrate) - float(state.winrate_at_step_start)
    if delta <= float(cfg.velocity_stall_epsilon):
        return False
    meaningful_delta = float(getattr(cfg, "plateau_evolution_meaningful_delta", 0.01))
    gap_to_gate = max(0.0, float(pass_target) - float(state.winrate_at_step_start))
    if gap_to_gate <= 0.0:
        return True
    progress_ratio = delta / gap_to_gate
    return delta >= meaningful_delta and progress_ratio >= _PLATEAU_GAP_PROGRESS_MIN


def sanitize_phantom_evolution_steps(
    state: PlateauState,
    *,
    max_steps: int | None = None,
) -> bool:
    """Cap evolution counter after checkpoint resume (legacy runs reached step 38+).

    When ``max_steps`` is set (certified/starship cap), use that as the hard ceiling
    so resume cannot sit above begin_evolution_step's TERMINAL threshold.
    """
    cap = len(EVOLUTION_STEP_ACTIONS)
    if max_steps is not None:
        cap = max(1, min(cap, int(max_steps)))
    if state.evolution_step <= cap:
        return False
    logger.warning(
        "birth.plateau.sanitize_phantom_steps step=%s capped=%s",
        state.evolution_step,
        cap,
    )
    state.evolution_step = cap
    state.evolution_rollouts_this_step = 0
    return True


def sanitize_stuck_plateau_evolution(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    current_winrate: float,
    pass_target: float | None = None,
) -> bool:
    """Unblock ladder when a checkpoint resumed with excessive rollouts on one step."""
    if not state.active or state.evolution_step <= 0:
        return False
    max_rollouts = int(getattr(cfg, "plateau_evolution_max_rollouts_per_step", 24))
    if state.evolution_rollouts_this_step <= max_rollouts * 2:
        return False
    target = float(pass_target if pass_target is not None else stage1_winrate_pass_threshold(cfg))
    if winrate_improvement_blocks_ladder(
        state,
        current_winrate=current_winrate,
        cfg=cfg,
        pass_target=target,
    ):
        return False
    state.evolution_rollouts_this_step = max(max_rollouts * 3, state.evolution_rollouts_this_step)
    logger.info(
        "birth.plateau.sanitize_stuck_evolution rollouts=%s max=%s winrate=%.2f%%",
        state.evolution_rollouts_this_step,
        max_rollouts,
        current_winrate * 100.0,
    )
    return True


def _compressed_ladder_active(
    *,
    cfg: BirthCurriculumConfig,
    stage_trades: int = 0,
    required: int = 0,
    compress: bool = False,
) -> bool:
    """True when evolution must run compressed (post volume-gate / hard-stop).

    Past the stage pass-gate volume, min_ppo + long rollout waits become thrash
    fuel. Compress as soon as ``stage_trades > required`` (or hard-stop), not only
    after the 3× beyond-gate multiplier.
    """
    if compress:
        return True
    if required > 0 and int(stage_trades) > int(required):
        return True
    if required > 0 and should_trades_beyond_gate_hard_stop(stage_trades, required, cfg):
        return True
    return False


def should_advance_evolution_step(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    current_winrate: float,
    pass_target: float | None = None,
    ppo_steps_since_step_start: int = 0,
    stage_trades: int = 0,
    required: int = 0,
    compress_ladder: bool = False,
) -> bool:
    if not state.active or state.evolution_step <= 0:
        return False
    compressed = _compressed_ladder_active(
        cfg=cfg,
        stage_trades=stage_trades,
        required=required,
        compress=compress_ladder,
    )
    min_ppo = int(getattr(cfg, "plateau_evolution_min_ppo_steps_between_steps", 0))
    if compressed:
        min_ppo = 0
    if min_ppo > 0 and int(ppo_steps_since_step_start) < min_ppo:
        return False
    min_rollouts = int(cfg.plateau_evolution_rollouts_per_step)
    if compressed:
        min_rollouts = max(
            1, int(getattr(cfg, "beyond_gate_evolution_rollouts_per_step", 4) or 4)
        )
    if state.evolution_rollouts_this_step < min_rollouts:
        return False
    target = float(pass_target if pass_target is not None else stage1_winrate_pass_threshold(cfg))
    if winrate_improvement_blocks_ladder(
        state,
        current_winrate=current_winrate,
        cfg=cfg,
        pass_target=target,
    ):
        return False
    return True


def should_force_advance_evolution_step(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    current_winrate: float,
    pass_target: float | None = None,
    ppo_steps_since_step_start: int = 0,
    stage_trades: int = 0,
    required: int = 0,
    compress_ladder: bool = False,
) -> bool:
    """Time-box fallback: force next evolution action after max rollouts without lift.

    ``min_ppo`` gates soft advance only. Once rollouts hit max without lift, force
    immediately — do not wait for min_ppo or max*3 (certified thrash root cause).
    """
    del ppo_steps_since_step_start  # soft-advance only; force is rollout-bounded
    if not state.active or state.evolution_step <= 0:
        return False
    max_noops = max(1, int(getattr(cfg, "plateau_evolution_max_noops_per_step", 3)))
    if state.evolution_noop_count >= max_noops:
        return True
    compressed = _compressed_ladder_active(
        cfg=cfg,
        stage_trades=stage_trades,
        required=required,
        compress=compress_ladder,
    )
    max_rollouts = int(getattr(cfg, "plateau_evolution_max_rollouts_per_step", 24))
    if compressed:
        max_rollouts = max(
            2, int(getattr(cfg, "beyond_gate_evolution_rollouts_per_step", 4) or 4) * 2
        )
    # Safety valve: always force after triple max even if WR is improving slowly.
    if state.evolution_rollouts_this_step >= max_rollouts * 3:
        return True
    if state.evolution_rollouts_this_step < max_rollouts:
        return False
    target = float(pass_target if pass_target is not None else stage1_winrate_pass_threshold(cfg))
    if winrate_improvement_blocks_ladder(
        state,
        current_winrate=current_winrate,
        cfg=cfg,
        pass_target=target,
    ):
        return False
    return True


def should_trigger_plateau_evolution_step(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    current_winrate: float,
    allow_start: bool = True,
    pass_target: float | None = None,
    ppo_steps_since_step_start: int = 0,
    stage_trades: int = 0,
    required: int = 0,
    compress_ladder: bool = False,
    max_steps: int | None = None,
    stage: Any = None,
) -> bool:
    if not state.active:
        return False
    if evolution_ladder_exhausted(state, stage=stage, max_steps=max_steps):
        return False
    if allow_start and should_start_evolution_step(state):
        return True
    if should_advance_evolution_step(
        state,
        cfg=cfg,
        current_winrate=current_winrate,
        pass_target=pass_target,
        ppo_steps_since_step_start=ppo_steps_since_step_start,
        stage_trades=stage_trades,
        required=required,
        compress_ladder=compress_ladder,
    ):
        return True
    return should_force_advance_evolution_step(
        state,
        cfg=cfg,
        current_winrate=current_winrate,
        pass_target=pass_target,
        ppo_steps_since_step_start=ppo_steps_since_step_start,
        stage_trades=stage_trades,
        required=required,
        compress_ladder=compress_ladder,
    )


def evolution_ladder_blocked_reason(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    current_winrate: float,
    remediation_exhausted: bool,
    trade_budget_remaining: int,
    stage_trades: int,
    required: int,
    pass_target: float | None = None,
    max_steps: int | None = None,
    stage: Any = None,
) -> str | None:
    if not state.active:
        return "plateau_inactive"
    if evolution_ladder_exhausted(state, stage=stage, max_steps=max_steps):
        return "ladder_exhausted"
    if should_block_plateau_recovery(
        state,
        cfg=cfg,
        remediation_exhausted=remediation_exhausted,
        trade_budget_remaining=trade_budget_remaining,
        stage_trades=stage_trades,
        required=required,
        max_steps=max_steps,
        stage=stage,
    ):
        return "recovery_blocked_budget_or_exhausted"
    if state.evolution_step <= 0:
        return None
    max_rollouts = int(getattr(cfg, "plateau_evolution_max_rollouts_per_step", 24))
    min_rollouts = int(cfg.plateau_evolution_rollouts_per_step)
    # H3: post volume-gate / compressed ladder uses shorter rollout gate
    if _compressed_ladder_active(
        cfg=cfg,
        stage_trades=stage_trades,
        required=required,
        compress=False,
    ):
        min_rollouts = int(
            getattr(cfg, "beyond_gate_evolution_rollouts_per_step", 4) or 4
        )
        max_rollouts = max(min_rollouts, min(max_rollouts, min_rollouts * 2))
    target = float(pass_target if pass_target is not None else stage1_winrate_pass_threshold(cfg))
    blocks = winrate_improvement_blocks_ladder(
        state,
        current_winrate=current_winrate,
        cfg=cfg,
        pass_target=target,
    )
    if state.evolution_rollouts_this_step < min_rollouts:
        return f"awaiting_rollouts {state.evolution_rollouts_this_step}/{min_rollouts}"
    if state.evolution_rollouts_this_step < max_rollouts:
        if blocks:
            return "winrate_improving"
        return f"awaiting_force_advance {state.evolution_rollouts_this_step}/{max_rollouts}"
    if state.evolution_rollouts_this_step < max_rollouts * 3 and blocks:
        return "winrate_improving"
    return None


def record_evolution_outcome(
    state: PlateauState,
    *,
    action: EvolutionAction,
    stage_trades: int,
    stage_wins: int,
    detail: str = "",
    applied: bool = True,
    rolling_winrate_500: float | None = None,
) -> None:
    winrate = float(stage_wins) / float(max(1, stage_trades))
    rolling = (
        float(rolling_winrate_500)
        if rolling_winrate_500 is not None
        else winrate
    )
    state.evolution_history.append(
        {
            "timestamp": time.time(),
            "step": int(state.evolution_step),
            "action": action.value,
            "winrate": round(winrate, 6),
            "rolling_winrate_500": round(rolling, 6),
            "trades": int(stage_trades),
            "detail": str(detail or ""),
            "applied": bool(applied),
        }
    )


def maybe_update_best_winrate(
    state: PlateauState,
    *,
    stage_trades: int,
    stage_wins: int,
    policy_path: str,
    cfg: BirthCurriculumConfig,
    rolling_winrate: float | None = None,
    rolling_source: str | None = None,
) -> bool:
    if not cfg.plateau_save_best_policy:
        return False
    min_trades = max(1, int(getattr(cfg, "plateau_best_policy_min_trades", 200)))
    if stage_trades < min_trades:
        return False
    updated = False
    winrate = float(stage_wins) / float(max(1, stage_trades))
    if winrate > state.best_winrate:
        state.best_winrate = winrate
        state.best_winrate_at_trade = int(stage_trades)
        if policy_path:
            state.best_policy_path = str(policy_path)
        updated = True
    # Raptor v14: track best rolling skill for rollback preference.
    src = str(rolling_source or "")
    if (
        rolling_winrate is not None
        and src in ("true_window", "partial_window")
        and float(rolling_winrate) > float(state.best_rolling_winrate)
    ):
        state.best_rolling_winrate = float(rolling_winrate)
        state.best_rolling_at_trade = int(stage_trades)
        if policy_path:
            state.best_rolling_policy_path = str(policy_path)
        updated = True
    return updated


def increment_evolution_rollout(state: PlateauState) -> None:
    if state.active:
        state.evolution_rollouts_this_step += 1
