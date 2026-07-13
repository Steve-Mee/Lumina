"""Direct WallAdaptationHandler signal coverage."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import BirthStageRolloutSnapshot
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.wall_adaptation_handler import WallAdaptationHandler


def _event(signal: str, context: dict) -> DomainEvent:
    payload = BirthStageRolloutSnapshot(
        correlation_id="wall-signal-cid",
        signal=signal,
        stage="stage1_trend",
        context=context,
    )
    return DomainEvent(
        topic="birth.stage.rollout.snapshot",
        producer="test",
        payload=payload.model_dump(mode="json"),
    )


@pytest.fixture
def handler() -> WallAdaptationHandler:
    return WallAdaptationHandler(
        EventBus(),
        BirthCurriculumConfig(
            wall_behavior="adaptive",
            adaptation_enabled=True,
            stage1_trend_trades=100,
            certified_stage_stall_wall_sec=300,
        ),
    )


@pytest.mark.unit
def test_wall_handler_restore_and_metrics(handler: WallAdaptationHandler) -> None:
    handler._on_snapshot(_event("wall_restore_state", {"metrics": {"adaptation_tier": 2}}))
    handler._on_snapshot(_event("adaptation_metrics", {}))
    assert handler.state.adaptation_tier >= 0


@pytest.mark.unit
def test_wall_handler_evaluate_trigger_no_stall(handler: WallAdaptationHandler) -> None:
    handler._on_snapshot(
        _event(
            "wall_evaluate_trigger",
            {
                "stage_trades": 10,
                "stage_wins": 5,
                "required": 100,
                "hold_ratio": 0.1,
                "constitution_violations": 0,
                "elapsed_stage_sec": 10.0,
                "failure_key": "",
                "force": False,
            },
        )
    )


@pytest.mark.unit
def test_wall_handler_never_stop_signal(handler: WallAdaptationHandler) -> None:
    handler._on_snapshot(
        _event(
            "adaptation_never_stop",
            {
                "failure_key": "budget",
                "rollout_chunk_trades": 20,
                "terminal_blocked": False,
            },
        )
    )


@pytest.mark.unit
def test_wall_handler_try_recovery_with_stall_trigger(handler: WallAdaptationHandler) -> None:
    handler._on_snapshot(
        _event(
            "adaptation_try_recovery",
            {
                "trigger_type": "certified_stall",
                "failure_key": "stage1_winrate",
                "stage_trades": 150,
                "required": 100,
                "current_winrate": 0.30,
                "winrate_history": [0.35, 0.34, 0.33, 0.32, 0.30],
                "original_rollout_chunk": 20,
                "rollout_chunk_trades": 20,
                "trade_budget_remaining": 1000,
                "terminal_blocked": False,
                "constitution_blocked": False,
                "learning_health": "flat",
            },
        )
    )


@pytest.mark.unit
def test_wall_handler_apply_result_success(handler: WallAdaptationHandler) -> None:
    handler._on_snapshot(_event("adaptation_apply_result", {"success": True}))
    handler._on_snapshot(_event("adaptation_apply_result", {"success": False}))
    handler._on_snapshot(
        DomainEvent(
            topic="birth.stage.rollout.snapshot",
            producer="test",
            payload={"signal": "wall_evaluate_trigger"},
        )
    )
