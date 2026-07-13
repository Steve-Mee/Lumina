"""Unit tests for adaptive parameter manager."""

from __future__ import annotations

import pytest

from lumina_core.birth.adaptive_parameter_manager import (
    WallAdaptationState,
    compute_parameter_patch,
)
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.meta_controller import LearningHealth


@pytest.fixture
def cfg() -> BirthCurriculumConfig:
    return BirthCurriculumConfig(
        winrate_trend_window=12,
        reward_trend_window=12,
        exploration_chunk_size=8,
    )


@pytest.mark.unit
def test_declining_health_widens_windows(cfg: BirthCurriculumConfig) -> None:
    patch = compute_parameter_patch(
        learning_health=LearningHealth.DECLINING,
        current_winrate_window=12,
        current_reward_window=12,
        cfg=cfg,
        post_volume_gate=True,
    )
    assert patch.winrate_trend_window == 14
    assert patch.reward_trend_window == 14
    assert patch.chunk_target is not None


@pytest.mark.unit
def test_improving_health_narrows_windows(cfg: BirthCurriculumConfig) -> None:
    patch = compute_parameter_patch(
        learning_health=LearningHealth.IMPROVING,
        current_winrate_window=16,
        current_reward_window=16,
        cfg=cfg,
    )
    assert patch.winrate_trend_window == 15
    assert patch.reward_trend_window == 15


@pytest.mark.unit
def test_recovery_rate_pct(cfg: BirthCurriculumConfig) -> None:
    state = WallAdaptationState(recovery_attempts=4, recovery_successes=3)
    assert state.autonomous_recovery_rate_pct == pytest.approx(75.0)
    metrics = state.to_metrics()
    assert metrics["autonomous_recovery_rate_pct"] == pytest.approx(75.0)
