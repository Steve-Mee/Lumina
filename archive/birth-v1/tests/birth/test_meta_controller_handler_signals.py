"""Direct MetaControllerHandler signal coverage via typed snapshots."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import BirthStageRolloutSnapshot
from lumina_core.birth.birth_bus_serde import serialize_learning_snapshot
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import LearningSnapshot
from lumina_core.birth.meta_controller_handler import MetaControllerHandler


def _snap() -> LearningSnapshot:
    return LearningSnapshot(
        winrate_history=(0.28, 0.27),
        reward_history=(0.05, 0.04),
        stage_trades=200,
        required_trades=500,
        patterns_mined=1,
        patterns_last_inject=0,
        oracle_wins_last_inject=0,
        buffer_size=64,
        escalation_level=0,
        strong_recovery_mode=False,
        strong_recovery_attempts=0,
        low_velocity_attempts=2,
        data_exhausted=False,
        stage=CurriculumStage.STAGE1_TREND,
        intra_hard_pct=None,
        range_flat_ratio=0.1,
        range_round_trips=4,
    )


def _event(signal: str, context: dict) -> DomainEvent:
    payload = BirthStageRolloutSnapshot(
        correlation_id="meta-signal-cid",
        signal=signal,
        stage=CurriculumStage.STAGE1_TREND.value,
        context=context,
    )
    return DomainEvent(
        topic="birth.stage.rollout.snapshot",
        producer="test",
        payload=payload.model_dump(mode="json"),
    )


@pytest.fixture
def handler() -> MetaControllerHandler:
    responses: dict[str, dict] = {}

    class _Registry:
        @staticmethod
        def set_response(cid: str, key: str, value: object) -> None:
            responses.setdefault(cid, {})[key] = value

    h = MetaControllerHandler(
        EventBus(),
        BirthCurriculumConfig(meta_controller_enabled=True),
        BirthRewardConfig(),
        registry=_Registry(),
    )
    h._responses = responses  # type: ignore[attr-defined]
    return h


@pytest.mark.unit
@pytest.mark.parametrize(
    "signal",
    [
        "meta_restore_state",
        "meta_observe",
        "meta_metrics_payload",
        "meta_scorecard_fields",
        "meta_decide",
        "meta_decide_pre_rollout",
        "meta_decide_after_rollout",
        "meta_decide_adaptation",
        "meta_decide_probe_rollout",
        "meta_decide_committed_rollout",
        "meta_on_probe_complete",
        "meta_maybe_start_self_eval",
        "meta_evaluate_provisional_fallback",
        "meta_apply_explore_multiplier",
        "meta_record_inject",
        "meta_patch_state",
        "meta_format_self_eval_suffix",
        "meta_self_eval_state",
        "meta_detect_stall",
    ],
)
def test_meta_handler_signals(handler: MetaControllerHandler, signal: str) -> None:
    snap = _snap()
    contexts: dict[str, dict] = {
        "meta_restore_state": {"metrics": {"rollouts_since_review": 2}},
        "meta_observe": {
            "winrate_history": [0.28, 0.27],
            "reward_history": [0.05, 0.04],
            "stage_trades": 200,
            "required_trades": 500,
            "patterns_mined": 1,
            "buffer_size": 64,
            "escalation_level": 0,
            "strong_recovery_mode": False,
            "strong_recovery_attempts": 0,
            "low_velocity_attempts": 2,
            "data_exhausted": False,
            "stage": "stage1_trend",
        },
        "meta_metrics_payload": {},
        "meta_scorecard_fields": {"plan": None},
        "meta_decide": {"trigger": "periodic", "snapshot": serialize_learning_snapshot(snap)},
        "meta_decide_pre_rollout": {
            "snapshot": serialize_learning_snapshot(snap),
            "base_explore_steps": 8,
        },
        "meta_decide_after_rollout": {"snapshot": serialize_learning_snapshot(snap)},
        "meta_decide_adaptation": {
            "snapshot": serialize_learning_snapshot(snap),
            "winrate": 0.27,
            "escalation_level": 0,
            "adaptation_tier": 0,
            "retries_this_stage": 0,
            "original_rollout_chunk": 250,
            "failure_key": "stall",
        },
        "meta_decide_probe_rollout": {"snapshot": serialize_learning_snapshot(snap)},
        "meta_decide_committed_rollout": {"snapshot": serialize_learning_snapshot(snap)},
        "meta_on_probe_complete": {
            "snapshot": serialize_learning_snapshot(snap),
            "probe_winrate": 0.33,
            "probe_trades": 8,
        },
        "meta_maybe_start_self_eval": {
            "snapshot": serialize_learning_snapshot(snap),
            "strong_recovery_attempts": 1,
            "attempt": 1,
        },
        "meta_evaluate_provisional_fallback": {
            "snapshot": serialize_learning_snapshot(snap),
            "constitution_violations": 0,
        },
        "meta_apply_explore_multiplier": {"explore_steps": 12},
        "meta_record_inject": {"patterns": 2, "oracle_wins": 1},
        "meta_patch_state": {"explore_multiplier": 1.2, "increment_rollouts": True},
        "meta_format_self_eval_suffix": {},
        "meta_self_eval_state": {},
        "meta_detect_stall": {
            "winrate_history": [0.28, 0.27],
            "reward_history": [0.05, 0.04],
            "low_velocity_attempts": 2,
        },
    }
    handler._on_snapshot(_event(signal, contexts[signal]))


@pytest.mark.unit
def test_meta_handler_invalid_snapshot_is_ignored(handler: MetaControllerHandler) -> None:
    handler._on_snapshot(
        DomainEvent(
            topic="birth.stage.rollout.snapshot",
            producer="test",
            payload={"signal": "meta_observe"},
        )
    )
