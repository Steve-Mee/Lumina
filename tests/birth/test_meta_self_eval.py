"""Meta-controller strategy probe self-evaluation."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import (
    BirthMetaController,
    LearningHealth,
    LearningSnapshot,
    RecoveryStrategy,
)
from lumina_core.birth.meta_self_eval import (
    SelfEvalPhase,
    SelfEvalState,
    StrategyProbeResult,
    build_probe_queue,
    score_probe_result,
    select_winner,
    should_start_self_eval,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = BirthCurriculumConfig(
        velocity_stall_attempt_threshold=5,
        velocity_stall_epsilon=0.002,
        meta_controller_enabled=True,
        meta_self_eval_enabled=True,
        meta_self_eval_min_stall_attempts=32,
        meta_self_eval_min_recovery_attempts=8,
        meta_self_eval_rollouts_per_strategy=12,
        meta_self_eval_min_velocity_gain=0.003,
        meta_self_eval_velocity_floor=0.002,
        meta_self_eval_cooldown_rollouts=20,
        intra_initial_hard_pct=0.15,
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def _reward_cfg() -> BirthRewardConfig:
    return BirthRewardConfig(expectancy_coeff=0.5)


def _controller(**cfg_overrides: object) -> BirthMetaController:
    return BirthMetaController(_cfg(**cfg_overrides), _reward_cfg())


def _stalled_snap(**overrides: object) -> LearningSnapshot:
    base = dict(
        winrate_history=(0.40, 0.40, 0.40, 0.40, 0.40, 0.40),
        reward_history=(0.01, 0.01, 0.01, 0.01, 0.01, 0.01),
        stage_trades=200,
        required_trades=150,
        patterns_mined=50,
        patterns_last_inject=10,
        oracle_wins_last_inject=2,
        buffer_size=300,
        escalation_level=1,
        strong_recovery_mode=True,
        strong_recovery_attempts=10,
        low_velocity_attempts=32,
        data_exhausted=False,
        stage=CurriculumStage.STAGE1_TREND,
        intra_hard_pct=0.25,
        attempt=50,
        combined_velocity=0.001,
        is_stalled=True,
        volume_gate_passed=True,
        learning_health=LearningHealth.FLAT,
    )
    base.update(overrides)
    return LearningSnapshot(**base)


@pytest.mark.unit
def test_should_start_on_prolonged_stall() -> None:
    cfg = _cfg()
    snap = _stalled_snap()
    state = SelfEvalState()
    assert should_start_self_eval(
        snap, state, cfg, strong_recovery_attempts=10, attempt=50
    )
    assert not should_start_self_eval(
        snap, state, cfg, strong_recovery_attempts=3, attempt=50
    )
    assert not should_start_self_eval(
        snap,
        SelfEvalState(phase=SelfEvalPhase.PROBING),
        cfg,
        strong_recovery_attempts=10,
        attempt=50,
    )
    assert not should_start_self_eval(
        snap,
        SelfEvalState(cooldown_until_attempt=60),
        cfg,
        strong_recovery_attempts=10,
        attempt=50,
    )


@pytest.mark.unit
def test_probe_queue_skips_data_when_exhausted() -> None:
    cfg = _cfg()
    snap = _stalled_snap(data_exhausted=True)
    queue = build_probe_queue(snap, cfg)
    assert "data_expansion" not in queue
    assert "intra_ease" in queue


@pytest.mark.unit
def test_probe_rotates_after_n_rollouts() -> None:
    ctrl = _controller(meta_self_eval_rollouts_per_strategy=3)
    snap = _stalled_snap()
    assert ctrl.maybe_start_self_eval(
        snap, strong_recovery_attempts=10, attempt=50
    )
    assert ctrl.self_eval.phase == SelfEvalPhase.PROBING
    first = ctrl.self_eval.current_strategy

    for i in range(2):
        post_snap = _stalled_snap(combined_velocity=0.001 + i * 0.0001)
        assert ctrl.on_probe_rollout_complete(post_snap, attempt=50 + i) is None
        assert ctrl.self_eval.current_strategy == first

    post_snap = _stalled_snap(combined_velocity=0.0015)
    result = ctrl.on_probe_rollout_complete(post_snap, attempt=53)
    assert result is None
    assert ctrl.self_eval.current_strategy != first
    assert len(ctrl.self_eval.probe_results) == 1


@pytest.mark.unit
def test_winner_by_velocity_delta() -> None:
    cfg = _cfg()
    results = [
        StrategyProbeResult(
            strategy="explore_boost",
            rollouts=12,
            velocity_start=0.001,
            velocity_end=0.004,
            velocity_delta=0.003,
            combined_at_end=0.004,
        ),
        StrategyProbeResult(
            strategy="pattern_inject_aggressive",
            rollouts=12,
            velocity_start=0.001,
            velocity_end=0.006,
            velocity_delta=0.005,
            combined_at_end=0.006,
        ),
    ]
    assert select_winner(results, cfg) == "pattern_inject_aggressive"
    assert score_probe_result(velocity_start=0.001, velocity_end=0.006) == pytest.approx(
        0.005
    )


@pytest.mark.unit
def test_select_winner_fallback_without_velocity_floor() -> None:
    cfg = _cfg()
    results = [
        StrategyProbeResult(
            strategy="pattern_inject_aggressive",
            rollouts=12,
            velocity_start=-62.795515,
            velocity_end=0.000259,
            velocity_delta=62.795774,
            combined_at_end=0.000259,
        ),
        StrategyProbeResult(
            strategy="explore_reduce",
            rollouts=12,
            velocity_start=7.8e-05,
            velocity_end=-8.3e-05,
            velocity_delta=-0.000162,
            combined_at_end=-8.3e-05,
        ),
    ]
    assert select_winner(results, cfg) == "pattern_inject_aggressive"


@pytest.mark.unit
def test_no_winner_exhausted_suggests_provisional() -> None:
    ctrl = _controller(meta_self_eval_rollouts_per_strategy=1)
    snap = _stalled_snap()
    ctrl.maybe_start_self_eval(snap, strong_recovery_attempts=10, attempt=50)
    queue_len = len(ctrl.self_eval.probe_queue)

    for i in range(queue_len):
        plan = ctrl.on_probe_rollout_complete(
            _stalled_snap(combined_velocity=0.001),
            attempt=60 + i,
        )
        if i < queue_len - 1:
            assert plan is None

    assert ctrl.self_eval.phase == SelfEvalPhase.EXHAUSTED
    assert plan is not None
    assert plan.suggest_provisional_pass is True


@pytest.mark.unit
def test_committed_strategy_used_after_probe() -> None:
    ctrl = _controller()
    ctrl.self_eval = SelfEvalState(
        phase=SelfEvalPhase.COMMITTED,
        committed_strategy="explore_boost",
    )
    plan = ctrl.decide_committed_rollout(_stalled_snap(combined_velocity=0.010))
    assert plan.self_eval_phase == SelfEvalPhase.COMMITTED.value
    assert plan.committed_strategy == "explore_boost"
    assert plan.primary == RecoveryStrategy.EXPLORE_BOOST


@pytest.mark.unit
def test_restore_self_eval_from_checkpoint() -> None:
    ctrl = _controller()
    metrics = {
        "meta_self_eval_phase": "committed",
        "meta_self_eval_committed_strategy": "explore_boost",
        "meta_self_eval_current_strategy": "",
        "meta_self_eval_probe_results": [
            {
                "strategy": "explore_boost",
                "rollouts": 12,
                "velocity_start": 0.001,
                "velocity_end": 0.008,
                "velocity_delta": 0.007,
                "combined_at_end": 0.008,
            }
        ],
        "meta_self_eval_cooldown_until_attempt": 0,
    }
    ctrl.restore_state(metrics)
    assert ctrl.self_eval.phase == SelfEvalPhase.COMMITTED
    assert ctrl.self_eval.committed_strategy == "explore_boost"
    assert len(ctrl.self_eval.probe_results) == 1


@pytest.mark.unit
def test_certified_blocks_provisional_with_log() -> None:
    ctrl = _controller()
    ctrl.self_eval = SelfEvalState(
        phase=SelfEvalPhase.EXHAUSTED,
        pending_provisional=True,
    )
    snap = _stalled_snap()
    prov = ctrl.evaluate_provisional_fallback(
        snap,
        allow_provisional=False,
        strong_recovery_attempts=10,
        stage_trades=200,
        required=150,
        attempt=5,
        patterns_mined=100,
        buffer_size=300,
        constitution_violations=0,
    )
    assert prov.should_grant is False
    assert prov.blocked_reason == "certified_mode_strict"
    assert prov.safeguards.get("self_eval_exhausted") is True
