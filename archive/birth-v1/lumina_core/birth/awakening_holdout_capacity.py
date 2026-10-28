"""Worst-case Awakening n_B slots on Birth holdout B (ADR-0049).

One walk. No stacked exams. No expand_data after freeze. Occupancy is empty-bar
fraction; worst legal density is 75% flat → 25% in-position at geometry hold.
"""
from __future__ import annotations

from math import floor
from typing import Any

from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX
from lumina_core.maturity.awakening.law import N_B_MIN

MIN_HOLD_BARS = 20


def worst_case_holdout_slots(holdout_ticks: int, hold_bars: int) -> int:
    ticks = max(0, int(holdout_ticks))
    bars = max(int(MIN_HOLD_BARS), int(hold_bars))
    if ticks <= 0:
        return 0
    return int(floor((1.0 - float(S3_OCCUPANCY_MAX)) * float(ticks) / float(bars)))


def awakening_holdout_capacity_ok(
    holdout_ticks: int,
    hold_bars: int,
    *,
    min_n_b: int = N_B_MIN,
) -> bool:
    return worst_case_holdout_slots(holdout_ticks, hold_bars) >= int(min_n_b)


def thin_holdout_reason(
    holdout_ticks: int,
    hold_bars: int,
    *,
    min_n_b: int = N_B_MIN,
) -> str | None:
    report = awakening_holdout_capacity_report(
        holdout_ticks, hold_bars, min_n_b=min_n_b
    )
    if report["ok"]:
        return None
    return (
        f"holdout_capacity_below_n_b_min slots={report['worst_case_slots']} "
        f"need={report['n_b_min']}"
    )


def awakening_holdout_capacity_report(
    holdout_ticks: int,
    hold_bars: int,
    *,
    min_n_b: int = N_B_MIN,
) -> dict[str, Any]:
    slots = worst_case_holdout_slots(holdout_ticks, hold_bars)
    need = int(min_n_b)
    return {
        "holdout_ticks": int(holdout_ticks),
        "hold_bars": max(int(MIN_HOLD_BARS), int(hold_bars)),
        "worst_case_slots": slots,
        "n_b_min": need,
        "ok": slots >= need,
    }


__all__ = [
    "MIN_HOLD_BARS",
    "awakening_holdout_capacity_ok",
    "awakening_holdout_capacity_report",
    "thin_holdout_reason",
    "worst_case_holdout_slots",
]
