"""Worst-case Awakening holdout slots. No floor cuts. No 150k-tick cheat."""
from __future__ import annotations

from lumina_core.birth.awakening_holdout_capacity import (
    awakening_holdout_capacity_ok,
    thin_holdout_reason,
    worst_case_holdout_slots,
)


def test_365d_holdout_hosts_n_b_min() -> None:
    assert worst_case_holdout_slots(290868, 120) == 605
    assert awakening_holdout_capacity_ok(290868, 120) is True
    assert thin_holdout_reason(290868, 120) is None


def test_min_exam_ticks_150k_cannot_host_500() -> None:
    assert worst_case_holdout_slots(150000, 120) == 312
    assert awakening_holdout_capacity_ok(150000, 120) is False
    reason = thin_holdout_reason(150000, 120)
    assert reason is not None
    assert "holdout_capacity_below_n_b_min" in reason


def test_hold_bars_floor_is_20() -> None:
    assert worst_case_holdout_slots(1000, 5) == worst_case_holdout_slots(1000, 20)
