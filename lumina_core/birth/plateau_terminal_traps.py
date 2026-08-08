"""Plateau terminal stall, recovery brake, phoenix, and trap detectors."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.plateau_enter import should_trades_beyond_gate_hard_stop
from lumina_core.birth.plateau_evolution_ladder import evolution_ladder_exhausted

if TYPE_CHECKING:
    from lumina_core.birth.plateau_escalator import PlateauState

TERMINAL_STALL_REASON = "plateau_evolution_exhausted"

_NO_LIFT_EPS = 1e-9


def should_brake_recovery_no_lift(
    state: PlateauState,
    *,
    eps: float = _NO_LIFT_EPS,
) -> bool:
    """True when a full ladder finished without improving best_winrate."""
    if not state.active or not evolution_ladder_exhausted(state):
        return False
    return float(state.best_winrate) <= float(state.best_winrate_at_cycle_start) + eps


def should_block_phoenix_no_lift(
    state: PlateauState,
    *,
    eps: float = _NO_LIFT_EPS,
) -> bool:
    """Fail-closed: block phoenix after no-lift ladder or completed cycle without lift."""
    if should_brake_recovery_no_lift(state, eps=eps):
        return True
    if int(state.full_recovery_cycles) < 1:
        return False
    return float(state.best_winrate) <= float(state.best_winrate_at_cycle_start) + eps


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
    # Full ladder with no best-winrate lift → stop recovery theater immediately.
    if should_brake_recovery_no_lift(state):
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


def detect_under_activity_trap(
    *,
    range_flat_ratio: float,
    range_total_signals: int,
    stage_trades: int,
    required: int,
    velocity_stall: bool,
    cfg: BirthCurriculumConfig,
) -> bool:
    """Stage 2: chronic flat position above pass band (under-participation).

    Opposite of over-trading: policy stays flat (~95%+) and never restores the
    30–70% flat band. Detect after volume gate (or on velocity stall) so
    explore/participation pressure runs before swarm escalation.
    """
    min_signals = int(getattr(cfg, "under_activity_min_range_signals", 50) or 50)
    if int(range_total_signals) < max(1, min_signals):
        return False
    past_gate = int(required) > 0 and int(stage_trades) >= int(required)
    if not past_gate and not velocity_stall:
        return False
    high = float(getattr(cfg, "under_activity_flat_threshold", 0.70) or 0.70)
    return float(range_flat_ratio) > high


def stage2_should_defer_swarm_for_flat_band(
    *,
    range_flat_ratio: float,
    range_total_signals: int,
    stage_trades: int,
    required: int,
    evolution_step: int,
    cfg: BirthCurriculumConfig,
) -> bool:
    """True when Stage2 flat-band failure must remediate before swarm tournament.

    Keeps swarm-first for Stage1/3; Stage2 treats flat-band survival as primary
    until ``stage2_flat_band_swarm_defer_steps`` evolution steps have run.
    """
    min_signals = int(getattr(cfg, "under_activity_min_range_signals", 50) or 50)
    if int(range_total_signals) < max(1, min_signals):
        return False
    if int(required) > 0 and int(stage_trades) < int(required):
        return False
    flat = float(range_flat_ratio)
    in_band = 0.30 - 1e-12 <= flat <= 0.70 + 1e-12
    if in_band:
        return False
    defer_steps = int(getattr(cfg, "stage2_flat_band_swarm_defer_steps", 2) or 2)
    return int(evolution_step) < max(0, defer_steps)


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
