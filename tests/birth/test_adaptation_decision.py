"""Unit tests for birth adaptive stall decision logic."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.meta_controller import get_adaptation_decision


@pytest.fixture
def cfg() -> BirthCurriculumConfig:
    return BirthCurriculumConfig(
        exploration_chunk_size=8,
        rollout_chunk_trades=250,
        negative_slope_threshold=-0.005,
        max_escalation_level=5,
    )


@pytest.mark.unit
def test_negative_trend_after_volume_gate_boosts_chunk(cfg: BirthCurriculumConfig) -> None:
    history = [0.35, 0.34, 0.33, 0.32, 0.30]
    decision = get_adaptation_decision(
        stage_trades=200,
        required=100,
        winrate=0.30,
        winrate_history=history,
        escalation_level=1,
        cfg=cfg,
    )
    assert decision.should_retry is True
    assert decision.reason == "negative_winrate_trend_after_volume_gate"
    assert decision.new_chunk_target == min(25, 8 * (1 + 1))
    assert "Negative trend" in decision.log_message


@pytest.mark.unit
def test_metrics_stall_without_negative_trend_uses_exploration_chunk(
    cfg: BirthCurriculumConfig,
) -> None:
    history = [0.30, 0.30, 0.30, 0.30, 0.30]
    decision = get_adaptation_decision(
        stage_trades=150,
        required=100,
        winrate=0.30,
        winrate_history=history,
        escalation_level=0,
        cfg=cfg,
    )
    assert decision.reason == "metrics_not_improving_within_wall"
    assert decision.new_chunk_target == cfg.exploration_chunk_size


@pytest.mark.unit
def test_pre_volume_gate_uses_rollout_chunk(cfg: BirthCurriculumConfig) -> None:
    decision = get_adaptation_decision(
        stage_trades=50,
        required=100,
        winrate=0.40,
        winrate_history=[0.40],
        escalation_level=0,
        cfg=cfg,
    )
    assert decision.reason == "default_stall_retry"
    assert decision.new_chunk_target == cfg.rollout_chunk_trades


@pytest.mark.unit
def test_short_history_treated_as_flat_trend(cfg: BirthCurriculumConfig) -> None:
    decision = get_adaptation_decision(
        stage_trades=120,
        required=100,
        winrate=0.28,
        winrate_history=[0.30, 0.29, 0.28],
        escalation_level=0,
        cfg=cfg,
    )
    assert decision.reason == "metrics_not_improving_within_wall"
