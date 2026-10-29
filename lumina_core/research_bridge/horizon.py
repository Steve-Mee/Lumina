"""D6: expected_horizon is required. No silent default (not 20, not oos_size)."""

from __future__ import annotations


class HorizonRefused(ValueError):
    """Missing or non-positive expected_horizon. SignalIntent is not logged as a fill."""


def require_expected_horizon_bars(value: object, *, oos_size: object = None) -> int:
    """Return a horizon >= 1. ``oos_size`` is never used as a fallback."""
    del oos_size  # D6: copying oos_size would be a silent default.
    if isinstance(value, bool) or not isinstance(value, int):
        raise HorizonRefused("expected_horizon is required and must be an int >= 1")
    if value < 1:
        raise HorizonRefused("expected_horizon is required and must be an int >= 1")
    return value
