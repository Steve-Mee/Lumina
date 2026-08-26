"""Birth SIM exit fills on close-only bars (no invented OHLC).

A stop order that is crossed by the close filled at the stop (±1 tick), not
at the close. Session/segment gaps fill at the gap bar close (true adverse).
Same-bar stop+target: stop wins (fail-closed).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.birth_trade_geometry import SEGMENT_BREAK_KEY

STOP_TARGET_SLIP_TICKS = 1.0


@dataclass(frozen=True, slots=True)
class BirthExitFill:
    reason: str
    mark_price: float
    slippage_ticks: float
    gap: bool


def row_is_segment_gap(row: dict[str, Any] | None) -> bool:
    if not isinstance(row, dict):
        return False
    return bool(row.get(SEGMENT_BREAK_KEY))


def birth_force_qty_one(curriculum_regime: str) -> bool:
    raw = str(curriculum_regime or "").strip().lower()
    return "stage1" in raw or raw == "trend"


def plan_birth_exit_fill(
    *,
    hit_stop: bool,
    hit_target: bool,
    flatten: bool,
    force_time: bool,
    force_flat: bool,
    close_price: float,
    stop_price: float,
    target_price: float,
    is_gap: bool,
) -> BirthExitFill | None:
    """Choose exit reason and mark. Stop beats target. Gap uses close, not stop."""
    if not (hit_stop or hit_target or flatten):
        return None
    px = float(close_price)
    if hit_stop:
        mark = px if is_gap else float(stop_price)
        return BirthExitFill("stop", mark, STOP_TARGET_SLIP_TICKS, bool(is_gap))
    if hit_target:
        mark = px if is_gap else float(target_price)
        return BirthExitFill("target", mark, STOP_TARGET_SLIP_TICKS, bool(is_gap))
    if force_time:
        return BirthExitFill("time_stop", px, STOP_TARGET_SLIP_TICKS, bool(is_gap))
    if force_flat:
        return BirthExitFill("force_exit", px, STOP_TARGET_SLIP_TICKS, bool(is_gap))
    return BirthExitFill("flatten", px, STOP_TARGET_SLIP_TICKS, bool(is_gap))


__all__ = [
    "BirthExitFill",
    "STOP_TARGET_SLIP_TICKS",
    "birth_force_qty_one",
    "plan_birth_exit_fill",
    "row_is_segment_gap",
]
