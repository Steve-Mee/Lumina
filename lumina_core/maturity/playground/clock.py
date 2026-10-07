"""Playground school clock. Five green days end it. A flat minute does not.

The clock stays open across quiet polls. It stops on a pass, on three
sustained stall windows, or when the operator stops it.
"""
from __future__ import annotations

from lumina_core.maturity.playground.law import N_D_SCHOOL
from lumina_core.maturity.playground.recovery import MAX_STALL_WINDOWS

__all__ = ["MAX_STALL_WINDOWS", "clock_keeps_running", "skill_clock_open"]


def skill_clock_open(*, green_days: int) -> bool:
    return int(green_days) < N_D_SCHOOL


def clock_keeps_running(
    *,
    passed: bool,
    stall_windows: int = 0,
    max_windows: int = MAX_STALL_WINDOWS,
) -> bool:
    if passed:
        return False
    if int(stall_windows) >= int(max_windows):
        return False
    return True
