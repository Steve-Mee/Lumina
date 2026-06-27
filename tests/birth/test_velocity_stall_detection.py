"""Velocity-based stall detection for birth curriculum learning."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.engine import BirthPhaseEngineV2
from lumina_core.birth.stage_scorecard import combined_learning_velocity, enrich_adaptation_payload


def _engine(tmp_path: Path) -> BirthPhaseEngineV2:
    return BirthPhaseEngineV2(
        runtime=SimpleNamespace(),
        ppo_trainer=SimpleNamespace(),
        market_data_service=SimpleNamespace(),
        workspace_root=tmp_path,
    )


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig(
        velocity_stall_attempt_threshold=5,
        velocity_stall_epsilon=0.002,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


@pytest.mark.unit
def test_detect_stall_increments_on_flat_velocity(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    cfg = _cfg(velocity_stall_attempt_threshold=5)
    flat_winrate = [0.40, 0.40, 0.40, 0.40, 0.40, 0.40]
    flat_reward = [0.01, 0.01, 0.01, 0.01, 0.01, 0.01]

    attempts = 0
    result = engine._detect_stall(
        winrate_history=flat_winrate,
        reward_history=flat_reward,
        low_velocity_attempts=attempts,
        cfg=cfg,
    )
    for _ in range(4):
        result = engine._detect_stall(
            winrate_history=flat_winrate,
            reward_history=flat_reward,
            low_velocity_attempts=result.low_velocity_attempts,
            cfg=cfg,
        )

    assert result.low_velocity_attempts == 5
    assert result.is_stalled is True
    assert result.combined_velocity == 0.0


@pytest.mark.unit
def test_detect_stall_resets_on_positive_trend(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    cfg = _cfg(velocity_stall_attempt_threshold=5)
    improving_winrate = [0.30, 0.32, 0.34, 0.36, 0.38, 0.42]
    improving_reward = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]

    after_flat = engine._detect_stall(
        winrate_history=[0.40] * 6,
        reward_history=[0.01] * 6,
        low_velocity_attempts=3,
        cfg=cfg,
    )
    assert after_flat.low_velocity_attempts == 4

    recovered = engine._detect_stall(
        winrate_history=improving_winrate,
        reward_history=improving_reward,
        low_velocity_attempts=after_flat.low_velocity_attempts,
        cfg=cfg,
    )
    assert recovered.low_velocity_attempts == 0
    assert recovered.is_stalled is False
    assert recovered.combined_velocity > cfg.velocity_stall_epsilon


@pytest.mark.unit
def test_detect_stall_negative_trend_counts_as_low_velocity(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    cfg = _cfg(velocity_stall_attempt_threshold=3)
    declining = [0.50, 0.48, 0.46, 0.44, 0.42, 0.40]

    result = engine._detect_stall(
        winrate_history=declining,
        reward_history=declining,
        low_velocity_attempts=0,
        cfg=cfg,
    )
    assert result.combined_velocity < 0.0
    assert result.low_velocity_attempts == 1


@pytest.mark.unit
def test_combined_learning_velocity_uses_min_when_both_available() -> None:
    winrate = [0.50, 0.49, 0.48, 0.47, 0.46, 0.45]
    reward = [0.10, 0.09, 0.08, 0.07, 0.06, 0.05]
    combined = combined_learning_velocity(winrate, reward)
    assert combined == pytest.approx(-0.01, abs=0.001)


@pytest.mark.unit
def test_certificate_thresholds_unchanged_after_detect_stall(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    before = engine.birth_config.certificate_thresholds.model_dump()
    cfg = _cfg(velocity_stall_attempt_threshold=2)

    engine._detect_stall(
        winrate_history=[0.40] * 6,
        reward_history=[0.01] * 6,
        low_velocity_attempts=1,
        cfg=cfg,
    )

    assert engine.birth_config.certificate_thresholds.model_dump() == before


@pytest.mark.unit
def test_enrich_adaptation_payload_exposes_velocity_fields() -> None:
    payload = enrich_adaptation_payload(
        stage_trades=2000,
        required=2000,
        winrate_history=[0.40] * 6,
        reward_history=[0.01] * 6,
        retries_this_stage=2,
        adaptation_history=[],
        adaptation_enabled=True,
        wall_behavior="adaptive",
        strong_recovery_mode=True,
        velocity_stall_attempts=12,
    )
    assert payload["strong_recovery_mode"] is True
    assert payload["velocity_stall_attempts"] == 12
    assert "learning_velocity_combined" in payload
