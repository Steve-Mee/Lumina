"""BirthMetaController: observation, recovery strategy, curriculum nudges."""

from __future__ import annotations

from dataclasses import replace

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import (
    BirthMetaController,
    LearningHealth,
    RecoveryStrategy,
    detect_stall,
    get_adaptation_decision,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig(
        velocity_stall_attempt_threshold=5,
        velocity_stall_epsilon=0.002,
        meta_improving_velocity_multiplier=1.5,
        meta_pattern_yield_floor=0.15,
        meta_controller_enabled=True,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _reward_cfg(**overrides: object) -> BirthRewardConfig:
    base = BirthRewardConfig(expectancy_coeff=0.5)
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _controller(**cfg_overrides: object) -> BirthMetaController:
    return BirthMetaController(_cfg(**cfg_overrides), _reward_cfg())


def _snap_inputs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "winrate_history": [0.30, 0.32, 0.34, 0.36, 0.38, 0.42],
        "reward_history": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06],
        "stage_trades": 200,
        "required_trades": 150,
        "patterns_mined": 50,
        "buffer_size": 300,
        "escalation_level": 1,
        "strong_recovery_mode": False,
        "strong_recovery_attempts": 0,
        "low_velocity_attempts": 0,
        "data_exhausted": False,
        "stage": CurriculumStage.STAGE1_TREND,
        "intra_hard_pct": 0.25,
        "attempt": 5,
    }
    base.update(overrides)
    return base


@pytest.mark.unit
def test_observe_improving_vs_stalled() -> None:
    ctrl = _controller()
    improving, stall_improving = ctrl.observe(**_snap_inputs())
    assert improving.learning_health == LearningHealth.IMPROVING
    assert stall_improving.is_stalled is False

    flat, stall_flat = ctrl.observe(
        **_snap_inputs(
            winrate_history=[0.40, 0.40, 0.40, 0.40, 0.40, 0.40],
            reward_history=[0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
            low_velocity_attempts=4,
        )
    )
    assert flat.learning_health == LearningHealth.FLAT
    assert stall_flat.is_stalled is True


@pytest.mark.unit
def test_decide_pattern_inject_on_low_yield() -> None:
    ctrl = _controller()
    ctrl.record_inject(patterns=10, oracle_wins=0)
    snap, _ = ctrl.observe(
        **_snap_inputs(
            winrate_history=[0.40, 0.40, 0.40, 0.40, 0.40, 0.40],
            reward_history=[0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
            low_velocity_attempts=5,
        )
    )
    plan = ctrl.decide_after_rollout(snap)
    assert plan.primary == RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE
    assert plan.mine is True
    assert plan.mine_aggressive is True


@pytest.mark.unit
def test_decide_explore_reduce_enters_strong_recovery() -> None:
    ctrl = _controller()
    ctrl.record_inject(patterns=20, oracle_wins=10)
    snap, _ = ctrl.observe(
        **_snap_inputs(
            winrate_history=[0.40, 0.40, 0.40, 0.40, 0.40, 0.40],
            reward_history=[0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
            low_velocity_attempts=5,
        )
    )
    plan = ctrl.decide_after_rollout(snap)
    assert plan.primary == RecoveryStrategy.EXPLORE_REDUCE
    assert plan.enter_strong_recovery is True


@pytest.mark.unit
def test_decide_reward_tweak_on_declining_reward() -> None:
    ctrl = _controller()
    ctrl.record_inject(patterns=20, oracle_wins=10)
    snap, _ = ctrl.observe(
        **_snap_inputs(
            winrate_history=[0.50, 0.48, 0.46, 0.44, 0.42, 0.40],
            reward_history=[0.10, 0.08, 0.06, 0.04, 0.02, 0.00],
            low_velocity_attempts=5,
        )
    )
    plan = ctrl.decide_after_rollout(snap)
    assert RecoveryStrategy.REWARD_SHAPING_TWEAK in plan.secondary
    assert plan.reward_tweak is not None
    assert plan.reward_tweak.expectancy_coeff > 0.5


@pytest.mark.unit
def test_intra_ease_on_flat_velocity() -> None:
    ctrl = _controller()
    ctrl.record_inject(patterns=20, oracle_wins=10)
    snap, _ = ctrl.observe(
        **_snap_inputs(
            winrate_history=[0.40, 0.40, 0.40, 0.40, 0.40, 0.40],
            reward_history=[0.01, 0.01, 0.01, 0.01, 0.01, 0.01],
            low_velocity_attempts=5,
            intra_hard_pct=0.30,
        )
    )
    plan = ctrl.decide_after_rollout(snap)
    assert RecoveryStrategy.INTRA_EASE in plan.secondary
    assert plan.intra_hard_pct_delta == pytest.approx(-0.05)


@pytest.mark.unit
def test_adaptation_wraps_existing_decision() -> None:
    ctrl = _controller()
    snap, _ = ctrl.observe(**_snap_inputs())
    plan = ctrl.decide_adaptation(
        snap,
        winrate=0.42,
        escalation_level=1,
        adaptation_tier=1,
        retries_this_stage=0,
        original_rollout_chunk=250,
        failure_key="stage1_winrate",
    )
    assert plan.primary == RecoveryStrategy.ADAPTATION_RETRY
    assert plan.adaptation is not None
    assert plan.adaptation.should_retry is True
    assert plan.mine is True


@pytest.mark.unit
def test_meta_disabled_pre_rollout_passthrough() -> None:
    ctrl = _controller(meta_controller_enabled=False)
    snap, _ = ctrl.observe(**_snap_inputs())
    plan = ctrl.decide_pre_rollout(
        snap,
        base_explore_steps=4000,
        wall_budget_exhausted=False,
        winrate_stagnation_count=0,
        hold_stagnation_count=0,
    )
    assert plan.explore_steps == 4000
    assert plan.primary == RecoveryStrategy.HOLD


@pytest.mark.unit
def test_detect_stall_parity_with_engine_helper() -> None:
    cfg = _cfg(velocity_stall_attempt_threshold=3)
    flat = [0.40, 0.40, 0.40, 0.40, 0.40, 0.40]
    result = detect_stall(
        winrate_history=flat,
        reward_history=flat,
        low_velocity_attempts=2,
        cfg=cfg,
    )
    assert result.low_velocity_attempts == 3
    assert result.is_stalled is True


@pytest.mark.unit
def test_get_adaptation_decision_negative_trend() -> None:
    cfg = _cfg()
    decision = get_adaptation_decision(
        stage_trades=200,
        required=150,
        winrate=0.40,
        winrate_history=[0.50, 0.48, 0.46, 0.44, 0.42, 0.40],
        escalation_level=1,
        cfg=cfg,
    )
    assert decision.reason == "negative_winrate_trend_after_volume_gate"


@pytest.mark.unit
def test_restore_state_persists_reward_tweak() -> None:
    ctrl = _controller()
    ctrl.restore_state({"meta_reward_expectancy_coeff": 0.6})
    assert ctrl.active_reward.expectancy_coeff == pytest.approx(0.6)
    assert ctrl.reward_tweak_active is True

    ctrl.restore_state({})
    tweaked = replace(ctrl.baseline_reward, expectancy_coeff=0.6)
    ctrl.active_reward = tweaked
    payload = ctrl.metrics_payload()
    assert payload["meta_reward_tweak_active"] is True


@pytest.mark.unit
def test_decide_review_periodic_declining_mines() -> None:
    ctrl = _controller()
    snap, _ = ctrl.observe(
        **_snap_inputs(
            winrate_history=[0.50, 0.48, 0.46, 0.44, 0.42, 0.40],
            reward_history=[0.10, 0.08, 0.06, 0.04, 0.02, 0.00],
        )
    )
    plan = ctrl.decide_review(snap, trigger="periodic")
    assert plan.trigger == "periodic"
    assert plan.mine is True
    assert plan.primary in {
        RecoveryStrategy.PATTERN_INJECT,
        RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE,
    }


@pytest.mark.unit
def test_decide_review_improving_explore_decay() -> None:
    ctrl = _controller(meta_explore_decay_improving=0.65)
    snap, _ = ctrl.observe(**_snap_inputs())
    plan = ctrl.decide_review(snap, trigger="periodic")
    assert plan.explore_steps_multiplier == pytest.approx(0.65)
    assert ctrl.explore_multiplier == pytest.approx(0.65)
    assert ctrl.apply_explore_multiplier(2000) == 1300


@pytest.mark.unit
def test_decide_review_intra_ramp_on_improving() -> None:
    ctrl = _controller(meta_intra_ramp_on_improving=True)
    snap, _ = ctrl.observe(**_snap_inputs())
    plan = ctrl.decide_review(snap, trigger="periodic")
    assert RecoveryStrategy.INTRA_RAMP in plan.secondary
    assert plan.intra_hard_pct_delta == pytest.approx(0.05)


@pytest.mark.unit
def test_format_decision_log_includes_rationale() -> None:
    ctrl = _controller()
    snap, _ = ctrl.observe(**_snap_inputs())
    plan = ctrl.decide_review(snap, trigger="periodic")
    payload = BirthMetaController.format_decision_log(plan, trigger="periodic")
    assert payload["trigger"] == "periodic"
    assert payload["rationale"]
    assert "combined_velocity" in payload
    assert payload["actions"]["explore_steps_multiplier"] <= 1.0


@pytest.mark.unit
def test_restore_explore_multiplier() -> None:
    ctrl = _controller()
    ctrl.restore_state({"meta_explore_multiplier": 0.55, "meta_review_trigger": "stall"})
    assert ctrl.explore_multiplier == pytest.approx(0.55)
    assert ctrl.last_review_trigger == "stall"
    payload = ctrl.metrics_payload()
    assert payload["meta_explore_multiplier"] == pytest.approx(0.55)
