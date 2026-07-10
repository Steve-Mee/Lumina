"""Death-spiral guard tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.death_spiral_guard import (
    build_stall_signature,
    should_widen_data_horizon,
    DeathSpiralState,
)


@pytest.mark.unit
def test_build_stall_signature_stable() -> None:
    sig = build_stall_signature(
        curriculum_stage="stage1_trend",
        blocker_metric="trend_winrate",
        blocker_value=0.4123,
    )
    assert "stage1_trend" in sig
    assert "0.41" in sig


@pytest.mark.unit
def test_should_widen_data_horizon() -> None:
    state = DeathSpiralState(circuit_breaker_tripped=True, novelty_budget=0)
    cfg = BirthCurriculumConfig(phoenix_widen_data_after_cycles=2)
    assert should_widen_data_horizon(state, phoenix_count=3, cfg=cfg) is True