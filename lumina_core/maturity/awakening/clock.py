"""Awakening skill clock — volume is necessary, not sufficient (ADR-0049)."""
from __future__ import annotations

from lumina_core.birth.foundation_metrics import S5_DD_MAX_PCT, S5_SHARPE_FLOOR
from lumina_core.maturity.awakening.law import (
    CLASS_INCONCLUSIVE,
    CLASS_REGRESS,
    N_B_MIN,
    STABLE,
    AwakeningSnapshot,
)

MAX_CYCLES = 8
MAX_STALL_RETRIES = 3
REGRESS_SHARPE_LE = -3.0


def skill_clock_open(snap: AwakeningSnapshot) -> bool:
    """Volume clock: n_B < 500. One eval walking holdout B is not a stop."""
    return int(snap.n_b) < N_B_MIN


def clock_keeps_running(
    snap: AwakeningSnapshot,
    *,
    cycle: int,
    max_cycles: int = MAX_CYCLES,
    stall_retries: int = 0,
    max_stall_retries: int = MAX_STALL_RETRIES,
    passed: bool = False,
) -> bool:
    """Keep training the child until AND, cycle budget, or stall budget.

    ``tape_exhausted`` means this eval finished holdout B. It is INCONCLUSIVE
    for n_B < 500, never a pass, and never a reason to throw away the child.
    """
    del snap
    if passed:
        return False
    if cycle >= int(max_cycles):
        return False
    if int(stall_retries) >= int(max_stall_retries):
        return False
    return True


def classify_stable(
    *,
    n_b: int,
    sharpe: float | None,
    dd_pct: float | None,
) -> str:
    """STABLE only at n_B ≥ 500. Holdout-exhausted at n=172 is not a pass."""
    if int(n_b) < N_B_MIN:
        return CLASS_INCONCLUSIVE
    if sharpe is None or dd_pct is None:
        return CLASS_INCONCLUSIVE
    s = float(sharpe)
    d = float(dd_pct)
    if s <= REGRESS_SHARPE_LE or d > S5_DD_MAX_PCT + 1e-12:
        return CLASS_REGRESS
    if s > S5_SHARPE_FLOOR and d <= S5_DD_MAX_PCT + 1e-12:
        return STABLE
    return CLASS_INCONCLUSIVE
