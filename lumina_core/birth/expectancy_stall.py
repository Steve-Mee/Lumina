"""Stage-2 expectancy stall: first-class quality trap (WR−0.50 below floor).

Occupancy may be in the 30–70% band while expectancy (≡ hygiene WR) fails.
Swarming without quality remediation burns into champion freeze. This module
detects the stall and recommends a bounded recovery ladder — never lowers floors.
"""

from __future__ import annotations

from typing import Any


def stage2_expectancy_live(
    *,
    stage_trades: int,
    stage_wins: int,
    rolling_winrate: float | None = None,
) -> float:
    """WR−0.50 proxy; prefer rolling when provided."""
    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    lifetime = float(wins) / float(max(1, trades)) if trades > 0 else 0.0
    if rolling_winrate is not None:
        return max(lifetime, float(rolling_winrate)) - 0.50
    return lifetime - 0.50


def detect_expectancy_stall(
    *,
    stage_is_range: bool,
    range_flat_ratio: float,
    range_total_signals: int,
    stage_trades: int,
    stage_wins: int,
    required: int,
    velocity_stall: bool = False,
    plateau_active: bool = False,
    trades_beyond_gate: int = 0,
    rolling_winrate: float | None = None,
    cfg: Any = None,
) -> bool:
    """True when volume/activity ok-ish but expectancy below stage2 floor."""
    if not stage_is_range:
        return False
    trades = int(stage_trades)
    req = max(1, int(required))
    if trades < req:
        return False
    signals = int(range_total_signals)
    flat = float(range_flat_ratio)
    # Activity near band (with soft margin): not chronic 95% flat / pure churn.
    if signals >= 50 and not (0.25 <= flat <= 0.75):
        return False
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        floor = float(stage2_expectancy_floor(cfg)) if cfg is not None else -0.15
    except Exception:
        floor = float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15) if cfg else -0.15
    exp = stage2_expectancy_live(
        stage_trades=trades,
        stage_wins=int(stage_wins),
        rolling_winrate=rolling_winrate,
    )
    if exp >= floor - 1e-12:
        return False
    # Pressure: beyond gate, plateau, or velocity stall.
    beyond = int(trades_beyond_gate)
    if beyond > 0 or plateau_active or velocity_stall:
        return True
    # Soft: past gate with clear gap.
    return (exp + 0.05) < floor


def recommended_expectancy_recovery_action(
    *,
    range_flat_ratio: float,
    remediation_step: int = 0,
) -> str:
    """Ordered ladder action id for meta / plateau surfaces."""
    step = max(0, int(remediation_step))
    flat = float(range_flat_ratio)
    if step <= 0:
        return "policy_rollback"
    if step == 1:
        return "expectancy_quality_reward"
    if step == 2:
        # Over-trade edge: reduce explore; under-flat already needs quality not more noise.
        return "explore_reduce" if flat <= 0.40 else "pattern_inject"
    if step == 3:
        return "pattern_inject"
    return "swarm_after_quality"


def stage2_should_defer_swarm_for_expectancy(
    *,
    expectancy_stall: bool,
    remediation_step: int,
    max_quality_steps: int = 4,
    evolution_step: int = 0,
    cfg: Any = None,
) -> bool:
    """Defer swarm while quality ladder still has budget (mirror flat-band defer)."""
    if not expectancy_stall:
        return False
    max_steps = int(
        getattr(cfg, "stage2_expectancy_quality_max_steps", max_quality_steps)
        if cfg is not None
        else max_quality_steps
    )
    max_steps = max(1, min(12, max_steps))
    # Allow swarm only after quality steps exhausted or evolution past defer window.
    defer_steps = int(
        getattr(cfg, "stage2_expectancy_swarm_defer_steps", 2) if cfg is not None else 2
    )
    if int(remediation_step) < max_steps and int(evolution_step) < max(1, defer_steps):
        return True
    return False


__all__ = [
    "detect_expectancy_stall",
    "recommended_expectancy_recovery_action",
    "stage2_expectancy_live",
    "stage2_should_defer_swarm_for_expectancy",
]
