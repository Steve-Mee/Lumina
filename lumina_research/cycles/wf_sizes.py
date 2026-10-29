"""Walk-forward IS/OOS sizes for 6-8 non-overlapping windows. Floor is 6."""

from __future__ import annotations

from lumina_research.validation.thresholds import FLOOR_MIN_OOS_WINDOWS
from lumina_research.validation.walk_forward import WalkForwardError

TARGET_OOS_WINDOWS = 8
WF_EMBARGO = 1


def walk_forward_sizes(n_obs: int, *, embargo: int = WF_EMBARGO) -> tuple[int, int, int]:
    """Return ``(is_size, oos_size, formed_windows)`` with 6 <= windows <= 8."""
    if n_obs < 8:
        raise WalkForwardError("not enough observations for walk-forward")
    if embargo < 0:
        raise WalkForwardError("embargo must be >= 0")
    for n_win in range(TARGET_OOS_WINDOWS, FLOOR_MIN_OOS_WINDOWS - 1, -1):
        oos_size = max(2, (n_obs - 40) // n_win)
        is_size = n_obs - embargo - n_win * oos_size
        if is_size < 2:
            continue
        formed = (n_obs - is_size - embargo) // oos_size
        if formed < FLOOR_MIN_OOS_WINDOWS or formed > TARGET_OOS_WINDOWS:
            continue
        if is_size + embargo + formed * oos_size > n_obs:
            continue
        return int(is_size), int(oos_size), int(formed)
    raise WalkForwardError(
        f"cannot form {FLOOR_MIN_OOS_WINDOWS}-{TARGET_OOS_WINDOWS} OOS windows from {n_obs} observations"
    )
