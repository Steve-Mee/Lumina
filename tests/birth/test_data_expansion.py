"""Birth data expansion ladder helpers."""

from __future__ import annotations

import pytest

from lumina_core.birth.data_expansion import (
    default_expansion_steps,
    expansion_ladder_at_max,
)


@pytest.mark.unit
def test_expansion_ladder_at_max_when_step_saturated() -> None:
    steps = default_expansion_steps()
    assert expansion_ladder_at_max(len(steps), steps, has_train_ticks=True) is True
    assert expansion_ladder_at_max(len(steps), steps, has_train_ticks=False) is False
    assert expansion_ladder_at_max(0, steps, has_train_ticks=True) is False


@pytest.mark.unit
def test_expansion_ladder_at_max_empty_steps() -> None:
    assert expansion_ladder_at_max(4, [], has_train_ticks=True) is False
