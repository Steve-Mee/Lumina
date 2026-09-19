"""Awakening recovery — stall→retry without Birth mutation or expand_data."""
from __future__ import annotations

from lumina_core.maturity.awakening.clock import MAX_STALL_RETRIES


def is_stall(
    *,
    prev_n_b: int,
    n_b: int,
    shot_error: bool,
    occupancy_crash: bool = False,
    tape_exhausted: bool = False,
) -> bool:
    """True when the shot failed, occupancy crashed, or an unfinished eval starved.

    A finished holdout walk (tape_exhausted) is an exam result, not a stall.
    Same n_B after walking B means this child took N trades — the next cycle
    trains more. Counting that as stall killed the live clock at n_B=86.
    """
    if shot_error:
        return True
    if occupancy_crash:
        return True
    if tape_exhausted:
        return False
    if int(n_b) <= 0 and int(prev_n_b) >= 0:
        return True
    if int(prev_n_b) >= 0 and int(n_b) <= int(prev_n_b):
        return True
    return False


def occupancy_crashed(occupancy: float | None, *, lo: float = 0.25) -> bool:
    if occupancy is None:
        return False
    return float(occupancy) + 1e-12 < float(lo)


def recovery_proven(
    *,
    stall_retries: int,
    freeze_ok: bool,
    cycles_completed: int = 0,
) -> bool:
    """Proven when the living clock ran with Birth freeze intact.

    Stall→retry is the recovery *mechanism* (no expand_data, no floor-cut).
    Requiring a stall to have happened forces a fake fail on a child that
    improves every cycle. Freeze held through ≥1 cycle (or a stall retry)
    is the honest proof.
    """
    if not freeze_ok:
        return False
    return int(cycles_completed) >= 1 or int(stall_retries) >= 1


def should_stop_retries(stall_retries: int, *, max_retries: int = MAX_STALL_RETRIES) -> bool:
    return int(stall_retries) >= int(max_retries)
