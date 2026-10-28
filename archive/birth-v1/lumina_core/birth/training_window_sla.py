"""C3: Training-window SLA — full requested history before Stage 2 budget burn.

Never green-light thin calendar coverage as a clean bootstrap.
"""

from __future__ import annotations

from typing import Any

# Plan default: ≥95% of requested calendar days (or explicit degraded_data_mode).
DEFAULT_TRAINING_WINDOW_MIN_RATIO = 0.95


def training_window_ratio(*, days_loaded: int, requested_days: int) -> float:
    """Return days_loaded / requested_days (1.0 if request is non-positive)."""
    req = int(requested_days or 0)
    loaded = max(0, int(days_loaded or 0))
    if req <= 0:
        return 1.0
    return float(loaded) / float(req)


def training_window_sla_ok(
    *,
    days_loaded: int,
    requested_days: int,
    min_ratio: float = DEFAULT_TRAINING_WINDOW_MIN_RATIO,
    degraded_data_mode: bool = False,
) -> bool:
    """True when calendar coverage meets SLA or operator allowed degraded mode."""
    if bool(degraded_data_mode):
        return True
    req = int(requested_days or 0)
    if req <= 0:
        return True
    loaded = int(days_loaded or 0)
    if loaded <= 0:
        return False
    ratio = float(min_ratio if min_ratio is not None else DEFAULT_TRAINING_WINDOW_MIN_RATIO)
    ratio = max(0.0, min(1.0, ratio))
    return training_window_ratio(days_loaded=loaded, requested_days=req) + 1e-12 >= ratio


def training_window_sla_report(
    *,
    days_loaded: int,
    requested_days: int,
    min_ratio: float = DEFAULT_TRAINING_WINDOW_MIN_RATIO,
    degraded_data_mode: bool = False,
) -> dict[str, Any]:
    """Structured SLA verdict for manifest / progress / tests."""
    loaded = int(days_loaded or 0)
    req = int(requested_days or 0)
    ratio = training_window_ratio(days_loaded=loaded, requested_days=req)
    ok = training_window_sla_ok(
        days_loaded=loaded,
        requested_days=req,
        min_ratio=min_ratio,
        degraded_data_mode=degraded_data_mode,
    )
    shortfall = max(0, req - loaded) if req > 0 else 0
    return {
        "schema": "training_window_sla_v1",
        "ok": bool(ok),
        "days_loaded": loaded,
        "requested_days": req,
        "ratio": round(ratio, 6),
        "min_ratio": float(min_ratio),
        "shortfall_days": int(shortfall),
        "degraded_data_mode": bool(degraded_data_mode),
        "stage2_entry_blocked": (not ok) and (not bool(degraded_data_mode)),
    }


def stage2_requires_data_expand(
    *,
    days_loaded: int,
    requested_days: int,
    min_ratio: float = DEFAULT_TRAINING_WINDOW_MIN_RATIO,
    degraded_data_mode: bool = False,
) -> bool:
    """True when Stage 2 must expand data (or operator fork) before burning gate trades."""
    return not training_window_sla_ok(
        days_loaded=days_loaded,
        requested_days=requested_days,
        min_ratio=min_ratio,
        degraded_data_mode=degraded_data_mode,
    )


__all__ = [
    "DEFAULT_TRAINING_WINDOW_MIN_RATIO",
    "training_window_ratio",
    "training_window_sla_ok",
    "training_window_sla_report",
    "stage2_requires_data_expand",
]
