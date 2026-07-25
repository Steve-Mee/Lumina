"""Learning plateau detection and bounded evolution escalator (ADR-0023)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage1_winrate_pass_threshold, stage_trade_target
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
    EvolutionAction.INTRA_EASY_ONLY: "Easy-only / stage skill explore (stage-aware)",
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
    evolution_noop_count: int = 0

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
            "plateau_evolution_noop_count": int(self.evolution_noop_count),
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
            evolution_noop_count=int(metrics.get("plateau_evolution_noop_count", 0) or 0),
        )


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


def evolution_ladder_exhausted(state: PlateauState) -> bool:
    """True when all real evolution actions (expand→phoenix) have been applied."""
    return state.evolution_step >= len(EVOLUTION_STEP_ACTIONS)


def evolution_actions_completed(state: PlateauState) -> int:
    return min(int(state.evolution_step), len(EVOLUTION_STEP_ACTIONS))


def evolution_phantom_steps(state: PlateauState) -> int:
    return max(0, int(state.evolution_step) - len(EVOLUTION_STEP_ACTIONS))


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


def rolling_winrate_from_chunks(
    chunks: list[tuple[int, int]] | list[list[int]] | None,
    *,
    window: int = 500,
    lifetime_wr: float = 0.0,
    min_covered_for_partial: int = 200,
    min_covered_for_true: int | None = None,
) -> tuple[float, str, int]:
    """Winrate over the last ``window`` trades from rollout (trades, wins) chunks.

    Returns (winrate, source, covered_trades) where source is one of:
    - true_window: covered >= ~window
    - partial_window: enough recent chunks but < full window
    - lifetime_fallback: not enough chunk history

    Raptor v13: sparse milestones often have no point at trades-window after
    resume → old baseline=0 collapsed rolling to lifetime. Chunks fix that.
    """
    win = max(1, int(window))
    true_need = int(min_covered_for_true) if min_covered_for_true is not None else win
    partial_need = max(1, int(min_covered_for_partial))
    life = float(lifetime_wr)
    if not chunks:
        return life, "lifetime_fallback", 0
    need = win
    covered = 0
    wins_acc = 0.0
    for item in reversed(list(chunks)):
        if covered >= need:
            break
        try:
            t = int(item[0])
            w = int(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if t <= 0:
            continue
        take = min(t, need - covered)
        # Proportional share if we only need part of the oldest chunk in the window.
        wins_acc += float(w) * (float(take) / float(t))
        covered += take
    if covered <= 0:
        return life, "lifetime_fallback", 0
    wr = float(wins_acc) / float(covered)
    if covered >= true_need:
        return wr, "true_window", covered
    if covered >= partial_need:
        return wr, "partial_window", covered
    return life, "lifetime_fallback", covered


def rolling_winrate_last_n_trades(
    *,
    stage_trades: int,
    stage_wins: int,
    wins_at_trade: dict[int, int],
    window: int = 500,
    chunks: list[tuple[int, int]] | list[list[int]] | None = None,
    return_meta: bool = False,
) -> float | tuple[float, str, int]:
    """Winrate over the last ``window`` stage trades.

    Prefer rollout chunks (Raptor v13). Fall back to milestone snapshots with
    hardened baseline (no silent lifetime collapse when milestones start late).
    """
    trades = int(stage_trades)
    wins = int(stage_wins)
    life = float(wins) / float(trades) if trades > 0 else 0.0
    if trades <= 0:
        return (0.0, "lifetime_fallback", 0) if return_meta else 0.0
    if trades <= window:
        return (life, "true_window", trades) if return_meta else life

    if chunks:
        wr, source, covered = rolling_winrate_from_chunks(
            chunks, window=window, lifetime_wr=life
        )
        if source != "lifetime_fallback":
            return (wr, source, covered) if return_meta else wr

    # Milestone path (hardened).
    boundary = trades - window
    keys = [int(t) for t in (wins_at_trade or {}) if int(t) > 0]
    if not keys:
        return (life, "lifetime_fallback", 0) if return_meta else life
    at_or_before = [t for t in keys if t <= boundary]
    if at_or_before:
        baseline_trades = max(at_or_before)
        baseline_wins = int(wins_at_trade.get(baseline_trades, 0))
        delta_trades = trades - baseline_trades
        if delta_trades <= 0:
            return (life, "lifetime_fallback", 0) if return_meta else life
        wr = float(wins - baseline_wins) / float(delta_trades)
        source = "true_window" if delta_trades >= window * 0.9 else "partial_window"
        return (wr, source, delta_trades) if return_meta else wr

    # No milestone at/before boundary: use earliest milestone (partial window
    # of known history after resume), never baseline=0 → lifetime lie.
    earliest = min(keys)
    if earliest >= trades:
        return (life, "lifetime_fallback", 0) if return_meta else life
    baseline_wins = int(wins_at_trade.get(earliest, 0))
    delta_trades = trades - earliest
    if delta_trades <= 0:
        return (life, "lifetime_fallback", 0) if return_meta else life
    wr = float(wins - baseline_wins) / float(delta_trades)
    source = (
        "true_window"
        if delta_trades >= window * 0.9
        else ("partial_window" if delta_trades >= 200 else "lifetime_fallback")
    )
    if source == "lifetime_fallback":
        return (life, "lifetime_fallback", delta_trades) if return_meta else life
    return (wr, source, delta_trades) if return_meta else wr


def prune_rolling_trade_chunks(
    chunks: list[tuple[int, int]],
    *,
    window: int = 500,
    max_chunks: int = 128,
) -> list[tuple[int, int]]:
    """Keep enough recent chunks to cover ~2× window (and max_chunks)."""
    if not chunks:
        return []
    cleaned: list[tuple[int, int]] = []
    for item in chunks:
        try:
            t, w = int(item[0]), int(item[1])
        except (TypeError, ValueError, IndexError):
            continue
        if t > 0:
            cleaned.append((t, max(0, w)))
    if not cleaned:
        return []
    need = max(1, int(window)) * 2
    kept: list[tuple[int, int]] = []
    total = 0
    for t, w in reversed(cleaned):
        kept.append((t, w))
        total += t
        if total >= need and len(kept) >= 2:
            break
        if len(kept) >= max_chunks:
            break
    kept.reverse()
    return kept


def revert_evolution_step_on_noop(state: PlateauState) -> None:
    """Undo ladder advance when an evolution action did not apply."""
    if state.evolution_step > 0:
        state.evolution_step -= 1
    state.evolution_rollouts_this_step = 0


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
    beyond = plateau_trades_beyond_gate(ctx.stage_trades, ctx.required)
    beyond_met = beyond >= plateau_max_trades_beyond_gate(ctx.required, cfg)
    # Dead-zone fix: once past beyond-gate hard stop, always enter plateau
    # even when winrate is "close" to target (e.g. 39% with gap=10pp → old code
    # blocked plateau forever between 35–45%). Gap only suppresses *early* entry.
    gap = float(cfg.plateau_winrate_gap)
    if not beyond_met and winrate >= pass_target - gap:
        return False
    slope = abs(float(ctx.winrate_trend_slope or 0.0))
    if not beyond_met and slope >= float(cfg.velocity_stall_epsilon):
        return False
    exhausted = str(ctx.meta_self_eval_phase or "").strip().lower() == "exhausted"
    velocity_met = ctx.velocity_stall_attempts >= int(cfg.velocity_stall_attempt_threshold)
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
    stage_trades: int = 0,
    required: int = 0,
) -> bool:
    """True when adaptive/never-stop recovery must stop (budget-gated never-stop).

    Beyond hard-stop alone does NOT block: the evolution ladder must still run.
    Block only after the ladder is exhausted (or max evolution steps reached).
    """
    if not state.active or not cfg.plateau_detection_enabled:
        return False
    beyond = required > 0 and should_trades_beyond_gate_hard_stop(
        stage_trades, required, cfg
    )
    if beyond and evolution_ladder_exhausted(state):
        return True
    if beyond and state.evolution_step >= int(cfg.plateau_max_evolution_steps):
        return True
    if state.evolution_step < int(cfg.plateau_max_evolution_steps):
        return False
    if evolution_ladder_exhausted(state):
        return True
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
    """Terminal when ladder is done, wall elapsed, or budget gone.

    Hard-stop beyond-gate no longer terminals *instantly* — that prevented the
    recovery ladder from finishing. Under hard-stop we use a compressed wall.
    """
    del meta_self_eval_phase
    if not state.active or not cfg.plateau_detection_enabled:
        return False
    if trade_budget_remaining is not None and int(trade_budget_remaining) <= 0:
        return True
    beyond = required > 0 and should_trades_beyond_gate_hard_stop(
        stage_trades, required, cfg
    )
    elapsed = plateau_elapsed_sec(state, now=now)
    if beyond:
        compressed_wall = float(
            getattr(cfg, "beyond_gate_plateau_wall_sec", 900) or 900
        )
        if evolution_ladder_exhausted(state):
            return True
        if state.evolution_step >= int(cfg.plateau_max_evolution_steps):
            return True
        if elapsed >= compressed_wall:
            return True
        return False
    if state.evolution_step < int(cfg.plateau_max_evolution_steps):
        return False
    if elapsed >= float(cfg.plateau_max_wall_sec):
        return True
    if evolution_ladder_exhausted(state):
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


_PLATEAU_GAP_PROGRESS_MIN = 0.25


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


def sanitize_phantom_evolution_steps(state: PlateauState) -> bool:
    """Cap evolution counter after checkpoint resume (legacy runs reached step 38+)."""
    cap = len(EVOLUTION_STEP_ACTIONS)
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
    """True when evolution must run compressed (beyond hard-stop recovery mode)."""
    if compress:
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
    """Time-box fallback: force next evolution action after max rollouts without lift."""
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
    if state.evolution_rollouts_this_step >= max_rollouts * 3:
        return True
    min_ppo = int(getattr(cfg, "plateau_evolution_min_ppo_steps_between_steps", 0))
    if compressed:
        min_ppo = 0
    if min_ppo > 0 and int(ppo_steps_since_step_start) < min_ppo:
        if state.evolution_rollouts_this_step < max_rollouts * 3:
            return False
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
) -> bool:
    if not state.active:
        return False
    if evolution_ladder_exhausted(state):
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
) -> str | None:
    if not state.active:
        return "plateau_inactive"
    if should_block_plateau_recovery(
        state,
        cfg=cfg,
        remediation_exhausted=remediation_exhausted,
        trade_budget_remaining=trade_budget_remaining,
        stage_trades=stage_trades,
        required=required,
    ):
        return "recovery_blocked_budget_or_exhausted"
    if state.evolution_step <= 0:
        return None
    max_rollouts = int(getattr(cfg, "plateau_evolution_max_rollouts_per_step", 24))
    min_rollouts = int(cfg.plateau_evolution_rollouts_per_step)
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


def detect_over_trading_trap(
    *,
    range_flat_ratio: float,
    range_round_trips: int,
    required: int,
    velocity_stall: bool,
    cfg: BirthCurriculumConfig,
) -> bool:
    """Stage 2: policy churns on range ticks (flat position far below pass band)."""
    if not velocity_stall:
        return False
    flat_threshold = float(getattr(cfg, "over_trading_flat_threshold", 0.30))
    if range_flat_ratio >= flat_threshold:
        return False
    min_trips = max(3, required // 10)
    trip_multiplier = float(getattr(cfg, "over_trading_round_trip_multiplier", 2.0))
    return range_round_trips >= int(min_trips * trip_multiplier)


def adaptation_stuck_escape_allowed(
    *,
    escapes_used: int,
    max_escapes: int,
    trade_budget_remaining: int,
) -> bool:
    """True when adaptation-stuck recovery may force a phoenix escape."""
    cap = int(max_escapes)
    if cap <= 0:
        return False
    return int(escapes_used) < cap and int(trade_budget_remaining) > 0


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
    if evolution_ladder_exhausted(state):
        return EvolutionAction.TERMINAL
    next_step = int(state.evolution_step) + 1
    next_action = action_for_step(next_step)
    if next_action == EvolutionAction.TERMINAL:
        state.evolution_step = len(EVOLUTION_STEP_ACTIONS)
        return EvolutionAction.TERMINAL
    state.evolution_step = next_step
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
) -> bool:
    if not cfg.plateau_save_best_policy:
        return False
    min_trades = max(1, int(getattr(cfg, "plateau_best_policy_min_trades", 200)))
    if stage_trades < min_trades:
        return False
    winrate = float(stage_wins) / float(max(1, stage_trades))
    if winrate <= state.best_winrate:
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
