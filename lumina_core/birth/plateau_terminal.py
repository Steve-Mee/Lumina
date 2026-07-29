"""Plateau terminal stall, evolution advance, and recovery brake helpers.

Bounded modules: ``plateau_terminal_ladder``, ``plateau_terminal_traps``.
"""
from __future__ import annotations

from lumina_core.birth.plateau_terminal_ladder import (  # noqa: F401
    evolution_ladder_blocked_reason,
    increment_evolution_rollout,
    maybe_update_best_winrate,
    record_evolution_outcome,
    revert_evolution_step_on_noop,
    sanitize_phantom_evolution_steps,
    sanitize_stuck_plateau_evolution,
    should_advance_evolution_step,
    should_force_advance_evolution_step,
    should_start_evolution_step,
    should_trigger_plateau_evolution_step,
    winrate_improvement_blocks_ladder,
)
from lumina_core.birth.plateau_terminal_traps import (  # noqa: F401
    TERMINAL_STALL_REASON,
    adaptation_stuck_escape_allowed,
    can_force_never_stop_recovery,
    detect_hold_trap,
    detect_over_trading_trap,
    plateau_elapsed_sec,
    record_forced_recovery,
    remediation_is_exhausted,
    should_block_phoenix_no_lift,
    should_block_plateau_recovery,
    should_brake_recovery_no_lift,
    should_phoenix_reset,
    should_terminal_plateau_stall,
)

__all__ = [
    "TERMINAL_STALL_REASON",
    "adaptation_stuck_escape_allowed",
    "can_force_never_stop_recovery",
    "detect_hold_trap",
    "detect_over_trading_trap",
    "evolution_ladder_blocked_reason",
    "increment_evolution_rollout",
    "maybe_update_best_winrate",
    "plateau_elapsed_sec",
    "record_evolution_outcome",
    "record_forced_recovery",
    "remediation_is_exhausted",
    "revert_evolution_step_on_noop",
    "sanitize_phantom_evolution_steps",
    "sanitize_stuck_plateau_evolution",
    "should_advance_evolution_step",
    "should_block_phoenix_no_lift",
    "should_block_plateau_recovery",
    "should_brake_recovery_no_lift",
    "should_force_advance_evolution_step",
    "should_phoenix_reset",
    "should_start_evolution_step",
    "should_terminal_plateau_stall",
    "should_trigger_plateau_evolution_step",
    "winrate_improvement_blocks_ladder",
]
