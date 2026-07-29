"""Birth data expansion ladder helpers."""

from __future__ import annotations

import pytest

from lumina_core.birth.data_expansion import (
    clamp_expansion_steps,
    default_expansion_steps,
    expansion_ladder_at_max,
)
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks


@pytest.mark.unit
def test_expansion_ladder_at_max_when_step_saturated() -> None:
    steps = default_expansion_steps()
    assert expansion_ladder_at_max(len(steps), steps, has_train_ticks=True) is True
    assert expansion_ladder_at_max(len(steps), steps, has_train_ticks=False) is False
    assert expansion_ladder_at_max(0, steps, has_train_ticks=True) is False


@pytest.mark.unit
def test_expansion_ladder_at_max_empty_steps() -> None:
    assert expansion_ladder_at_max(4, [], has_train_ticks=True) is False


@pytest.mark.unit
def test_clamp_expansion_steps_to_max_real_days() -> None:
    clamped = clamp_expansion_steps([90, 180, 365, 730], max_real_days=112)
    assert clamped == [90, 112]
    assert max(clamped) == 112
    assert all(d <= 112 for d in clamped)


@pytest.mark.unit
def test_actual_calendar_days_from_ticks() -> None:
    ticks = [
        {"timestamp": "2026-07-01T00:00:00+00:00"},
        {"timestamp": "2026-07-10T12:00:00+00:00"},
    ]
    assert actual_calendar_days_from_ticks(ticks) == 10
    assert actual_calendar_days_from_ticks([]) == 0
