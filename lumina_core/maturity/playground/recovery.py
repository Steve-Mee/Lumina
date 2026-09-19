"""Playground recovery — stall→retry without wipe, expand_data, or floor-cut."""
from __future__ import annotations

MAX_STALL_RETRIES = 3


def is_stall(
    *,
    prev_n_p: int,
    n_p: int,
    occupancy_crash: bool = False,
    habitat_error: bool = False,
    waiting_operator: bool = False,
) -> bool:
    if waiting_operator:
        return False
    if habitat_error:
        return True
    if occupancy_crash:
        return True
    if int(prev_n_p) >= 0 and int(n_p) < int(prev_n_p):
        return True
    if int(prev_n_p) >= 0 and int(n_p) == int(prev_n_p):
        return True
    return False


def occupancy_crashed(occupancy: float | None, *, lo: float = 0.25) -> bool:
    if occupancy is None:
        return False
    return float(occupancy) + 1e-12 < float(lo)


def recovery_proven(*, freeze_ok: bool, cycles_completed: int = 0, stall_retries: int = 0) -> bool:
    if not freeze_ok:
        return False
    return int(cycles_completed) >= 1 or int(stall_retries) >= 1


def should_stop_retries(stall_retries: int, *, max_retries: int = MAX_STALL_RETRIES) -> bool:
    return int(stall_retries) >= int(max_retries)
