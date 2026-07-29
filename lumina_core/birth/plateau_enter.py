"""Plateau entry, quarantine, and trades-beyond-gate helpers."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage_trade_target
from lumina_core.logging_utils import get_logger

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState

logger = get_logger("lumina.birth.plateau_enter")


def plateau_trades_beyond_gate(stage_trades: int, required: int) -> int:
    return max(0, int(stage_trades) - int(required))


def plateau_max_trades_beyond_gate(required: int, cfg: BirthCurriculumConfig) -> int:
    mult = max(1, int(cfg.plateau_trades_beyond_gate_multiplier))
    return int(required) * mult


def should_trades_beyond_gate_hard_stop(
    stage_trades: int,
    required: int,
    cfg: BirthCurriculumConfig,
) -> bool:
    """Force terminal when stage trades exceed pass gate by configured multiplier."""
    return plateau_trades_beyond_gate(stage_trades, required) >= plateau_max_trades_beyond_gate(
        required, cfg
    )


@dataclass(slots=True)
class PlateauEnterContext:
    stage_trades: int
    stage_wins: int
    required: int
    winrate_trend_slope: float | None
    velocity_stall_attempts: int
    meta_self_eval_phase: str
    pass_metric_target: float = 0.45
    plateau_quarantine_active: bool = False
    stage: CurriculumStage = CurriculumStage.STAGE1_TREND
    # Starship: EdgeScore-aware early enter (wall / flat health) — not vanity WR wait.
    wall_budget_exhausted: bool = False
    meta_learning_health: str = ""
    skill_failing: bool | None = None


def plateau_min_stage_trades(stage: CurriculumStage, cfg: BirthCurriculumConfig) -> int:
    """Minimum stage trades before plateau detection (fraction of full budget).

    Stage3 mixed: allow plateau as soon as pass-gate volume is met so recovery
    can start when WR/hold floors fail (Raptor v8 — no wait until 25% of 5000).
    """
    from lumina_core.birth.curriculum import stage_pass_trades

    floor = stage_pass_trades(stage, cfg)
    if stage == CurriculumStage.STAGE3_MIXED:
        return floor
    target = stage_trade_target(stage, cfg)
    pct = float(getattr(cfg, "plateau_min_stage_trades_pct", 0.25))
    return max(floor, int(round(float(target) * max(0.05, min(1.0, pct)))))


def apply_plateau_quarantine_on_resume(
    *,
    cfg: BirthCurriculumConfig,
    stage_trades: int,
    required: int | None = None,
) -> dict[str, Any]:
    """Grace period after checkpoint resume — blocks instant plateau re-entry.

    When the run is already past the trades-beyond-gate hard stop, quarantine is
    skipped: recovery (plateau ladder / policy rollback) must start immediately.
    """
    req = int(required) if required is not None else 0
    if req > 0 and should_trades_beyond_gate_hard_stop(int(stage_trades), req, cfg):
        logger.warning(
            "birth.plateau.quarantine skipped reason=beyond_hard_stop trades=%s required=%s max_beyond=%s",
            stage_trades,
            req,
            plateau_max_trades_beyond_gate(req, cfg),
        )
        return {
            "plateau_quarantine_active": False,
            "plateau_quarantine_rollouts_remaining": 0,
            "plateau_quarantine_trades_remaining": 0,
            "plateau_quarantine_trades_at_resume": int(stage_trades),
            "plateau_quarantine_skipped_reason": "beyond_hard_stop",
        }
    return {
        "plateau_quarantine_active": True,
        "plateau_quarantine_rollouts_remaining": int(cfg.plateau_quarantine_rollouts),
        "plateau_quarantine_trades_remaining": int(cfg.plateau_quarantine_min_trades),
        "plateau_quarantine_trades_at_resume": int(stage_trades),
        "plateau_quarantine_skipped_reason": "",
    }


def is_plateau_quarantine_blocking(
    *,
    quarantine_rollouts_remaining: int,
    quarantine_trades_at_resume: int,
    stage_trades: int,
    quarantine_min_trades: int,
) -> bool:
    if int(quarantine_rollouts_remaining) > 0:
        return True
    new_trades = max(0, int(stage_trades) - int(quarantine_trades_at_resume))
    return new_trades < int(quarantine_min_trades)


def update_plateau_quarantine_after_rollout(
    quarantine: dict[str, Any],
    *,
    stage_trades: int,
) -> bool:
    """Decrement quarantine; return True while plateau entry remains blocked."""
    if not quarantine.get("plateau_quarantine_active"):
        return False
    rem = int(quarantine.get("plateau_quarantine_rollouts_remaining", 0) or 0)
    if rem > 0:
        quarantine["plateau_quarantine_rollouts_remaining"] = rem - 1
    trades_at = int(quarantine.get("plateau_quarantine_trades_at_resume", 0) or 0)
    min_new = int(quarantine.get("plateau_quarantine_trades_remaining", 0) or 0)
    new_trades = max(0, int(stage_trades) - trades_at)
    rollouts_done = int(quarantine.get("plateau_quarantine_rollouts_remaining", 0) or 0) <= 0
    trades_done = new_trades >= min_new
    if rollouts_done and trades_done:
        quarantine["plateau_quarantine_active"] = False
        return False
    return True

def _plateau_skill_failing(ctx: PlateauEnterContext, *, cfg: BirthCurriculumConfig) -> bool:
    """True when stage skill gate fails (EdgeScore hygiene floor when enabled)."""
    if ctx.skill_failing is not None:
        return bool(ctx.skill_failing)
    winrate = float(ctx.stage_wins) / float(max(1, ctx.stage_trades))
    edgescore_on = bool(
        (
            ctx.stage == CurriculumStage.STAGE1_TREND
            and getattr(cfg, "stage1_edgescore_enabled", False)
        )
        or (
            ctx.stage == CurriculumStage.STAGE3_MIXED
            and getattr(cfg, "stage3_edgescore_enabled", False)
        )
    )
    if edgescore_on and ctx.stage in (
        CurriculumStage.STAGE1_TREND,
        CurriculumStage.STAGE3_MIXED,
    ):
        if ctx.stage == CurriculumStage.STAGE3_MIXED:
            floor = float(getattr(cfg, "stage3_winrate_floor", 0.35) or 0.35)
        else:
            floor = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35) or 0.35)
        return winrate + 1e-9 < floor
    return winrate + 1e-9 < float(ctx.pass_metric_target)


def should_enter_plateau(ctx: PlateauEnterContext, *, cfg: BirthCurriculumConfig) -> bool:
    if not cfg.plateau_detection_enabled:
        return False
    if ctx.plateau_quarantine_active:
        return False
    min_trades = plateau_min_stage_trades(ctx.stage, cfg)
    if ctx.stage_trades < min_trades:
        return False
    if ctx.stage_trades < ctx.required:
        return False
    winrate = float(ctx.stage_wins) / float(max(1, ctx.stage_trades))
    pass_target = float(ctx.pass_metric_target)
    # Already at/above pass target → graduation path, not plateau recovery.
    if winrate >= pass_target:
        return False
    skill_failing = _plateau_skill_failing(ctx, cfg=cfg)
    # Hygiene floor already cleared but vanity target not yet — keep learning window.
    if not skill_failing:
        # Legacy near-target path still applies below; do not force theater.
        pass
    beyond = plateau_trades_beyond_gate(ctx.stage_trades, ctx.required)
    beyond_met = beyond >= plateau_max_trades_beyond_gate(ctx.required, cfg)
    exhausted = str(ctx.meta_self_eval_phase or "").strip().lower() == "exhausted"
    velocity_met = ctx.velocity_stall_attempts >= int(cfg.velocity_stall_attempt_threshold)
    wall_exhausted = bool(ctx.wall_budget_exhausted)
    health = str(ctx.meta_learning_health or "").strip().lower()
    flat_health = health in ("flat", "declining")
    # Starship: wall exhausted / flat health + skill failing → enter without vanity wait.
    if skill_failing and (wall_exhausted or (flat_health and beyond > 0)):
        return True
    # Dead-zone fix: once past beyond-gate hard stop, always enter plateau
    # even when winrate is "close" to target (e.g. 39% with gap=10pp → old code
    # blocked plateau forever between 35–45%). Gap only suppresses *early* entry.
    gap = float(cfg.plateau_winrate_gap)
    if not beyond_met and winrate >= pass_target - gap:
        return False
    slope = abs(float(ctx.winrate_trend_slope or 0.0))
    if not beyond_met and slope >= float(cfg.velocity_stall_epsilon):
        return False
    if not (exhausted or velocity_met or beyond_met):
        return False
    return True


def sanitize_plateau_best_snapshot(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
    stage_trades: int,
    stage_wins: int,
) -> None:
    """Drop statistically meaningless best-policy spikes; re-anchor to current winrate."""
    min_trades = max(1, int(getattr(cfg, "plateau_best_policy_min_trades", 200)))
    if state.best_winrate_at_trade > 0 and state.best_winrate_at_trade < min_trades:
        logger.warning(
            "birth.plateau.best_snapshot_cleared stale_trades=%s min=%s winrate=%.1f%%",
            state.best_winrate_at_trade,
            min_trades,
            state.best_winrate * 100.0,
        )
        state.best_winrate = 0.0
        state.best_winrate_at_trade = 0
        state.best_policy_path = ""
    if stage_trades >= min_trades:
        current_wr = float(stage_wins) / float(max(1, stage_trades))
        if current_wr > state.best_winrate:
            state.best_winrate = current_wr
            state.best_winrate_at_trade = int(stage_trades)


def is_valid_best_policy_snapshot(
    state: PlateauState,
    *,
    cfg: BirthCurriculumConfig,
) -> bool:
    min_trades = max(1, int(getattr(cfg, "plateau_best_policy_min_trades", 200)))
    path = str(state.best_policy_path or "").strip()
    return (
        bool(path)
        and state.best_winrate_at_trade >= min_trades
        and state.best_winrate > 0.0
    )

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
    state.best_winrate_at_cycle_start = float(state.best_winrate)
    logger.warning(
        "birth.plateau.entered trades=%s winrate=%.2f%% best_at_cycle_start=%.2f%%",
        stage_trades,
        winrate * 100.0,
        state.best_winrate_at_cycle_start * 100.0,
    )


def reset_plateau_for_new_cycle(state: PlateauState, *, stage_trades: int, stage_wins: int) -> None:
    """Restart evolution ladder after remediation cycle while keeping best snapshot."""
    state.active = True
    state.evolution_step = 0
    state.evolution_rollouts_this_step = 0
    state.forced_recoveries_count = 0
    state.winrate_at_step_start = float(stage_wins) / float(max(1, stage_trades))
    state.full_recovery_cycles += 1
    state.best_winrate_at_cycle_start = float(state.best_winrate)
    logger.warning(
        "birth.plateau.cycle_reset cycle=%s trades=%s winrate=%.2f%% best_at_cycle_start=%.2f%%",
        state.full_recovery_cycles,
        stage_trades,
        state.winrate_at_step_start * 100.0,
        state.best_winrate_at_cycle_start * 100.0,
    )
