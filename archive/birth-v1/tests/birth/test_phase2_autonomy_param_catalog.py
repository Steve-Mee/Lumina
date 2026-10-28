"""Safe birth param catalog tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.adaptive_parameter_manager import WallAdaptationState
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.meta_controller import LearningHealth
from lumina_core.birth.phase2_autonomy.param_catalog import (
    FORBIDDEN_PARAM_KEYS,
    apply_param_proposal_to_state,
    clamp_param_value,
    propose_param_adjustment,
    validate_param_changes,
)


@pytest.mark.unit
def test_forbidden_keys_detected() -> None:
    assert "max_risk_percent" in FORBIDDEN_PARAM_KEYS
    violations = validate_param_changes({"max_risk_percent": 1.0})
    assert any(v.startswith("forbidden:") for v in violations)


@pytest.mark.unit
def test_out_of_bounds_detected() -> None:
    violations = validate_param_changes({"winrate_trend_window": 100})
    assert any("out_of_bounds" in v for v in violations)


@pytest.mark.unit
def test_clamp_param_value() -> None:
    assert clamp_param_value("winrate_trend_window", 100) == 24
    assert clamp_param_value("winrate_trend_window", 1) == 5
    assert clamp_param_value("max_risk_percent", 0.5) is None


@pytest.mark.unit
def test_propose_declining_widens_windows() -> None:
    cfg = BirthCurriculumConfig(winrate_trend_window=12, reward_trend_window=12)
    prop = propose_param_adjustment(
        learning_health=LearningHealth.DECLINING,
        current_winrate_window=12,
        current_reward_window=12,
        cfg=cfg,
        post_volume_gate=True,
    )
    assert prop.risk_touching is False
    if prop.changes:
        assert validate_param_changes(prop.changes) == []


@pytest.mark.unit
def test_apply_to_state() -> None:
    state = WallAdaptationState(effective_winrate_window=12, effective_reward_window=12)
    prop = propose_param_adjustment(
        learning_health=LearningHealth.DECLINING,
        current_winrate_window=12,
        current_reward_window=12,
        cfg=BirthCurriculumConfig(),
    )
    apply_param_proposal_to_state(state, prop)
    if "winrate_trend_window" in prop.changes:
        assert state.effective_winrate_window == int(prop.changes["winrate_trend_window"])
