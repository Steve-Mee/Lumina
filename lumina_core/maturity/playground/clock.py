"""Playground skill clock — n_P is necessary, not sufficient (ADR-0050)."""
from __future__ import annotations

from lumina_core.maturity.playground.law import N_P_MIN

MAX_STALL_RETRIES = 3


def skill_clock_open(*, n_p: int) -> bool:
    return int(n_p) < N_P_MIN


def clock_keeps_running(
    *,
    passed: bool,
    stall_retries: int = 0,
    max_stall_retries: int = MAX_STALL_RETRIES,
) -> bool:
    if passed:
        return False
    if int(stall_retries) >= int(max_stall_retries):
        return False
    return True
