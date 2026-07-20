"""Phase 2 orchestrator: disabled default + gated apply."""

from __future__ import annotations

from typing import Any

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.adaptive_parameter_manager import WallAdaptationState
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.phase2_autonomy.contracts import Phase2GateReason
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.orchestrator import (
    Phase2AutonomyOrchestrator,
    build_orchestrator_from_cfg,
)


class _FakeTwin:
    def evaluate_dna_promotion(self, _dna: Any) -> dict[str, Any]:
        return {
            "confidence": 0.9,
            "recommendation": True,
            "executable": True,
            "effective_recommendation": True,
            "mode": "full_auto",
            "risk_flags": [],
        }


@pytest.mark.unit
def test_build_returns_none_when_disabled() -> None:
    cfg = BirthCurriculumConfig(phase2_autonomy_enabled=False)
    assert build_orchestrator_from_cfg(cfg) is None


@pytest.mark.unit
def test_default_features_inactive() -> None:
    orch = Phase2AutonomyOrchestrator()
    assert orch.is_active() is False
    decision = orch.evaluate_dynamic_wall(stage="STAGE1_TREND", stage_trades=100, required=100)
    assert decision.gate is not None
    assert decision.gate.allowed is False
    assert decision.gate.reason == Phase2GateReason.FEATURE_DISABLED.value
    assert decision.applied is False


@pytest.mark.unit
def test_disabled_does_not_publish() -> None:
    bus = EventBus()
    orch = Phase2AutonomyOrchestrator(
        features=Phase2AutonomyFeatures(enabled=False),
        event_bus=bus,
    )
    orch.evaluate_dynamic_wall(correlation_id="c1", stage="S1")
    assert bus.history("birth.phase2.wall.proposal", limit=5) == []
    assert bus.history("birth.phase2.gate.result", limit=5) == []


@pytest.mark.unit
def test_enabled_scaffold_proposes_and_publishes() -> None:
    bus = EventBus()
    features = Phase2AutonomyFeatures(
        enabled=True,
        dynamic_wall_enabled=True,
        require_perfect_birth_flag=False,
        require_twin_for_apply=False,
        allow_sim_scaffold=True,
        execution_mode="apply",
    )
    orch = Phase2AutonomyOrchestrator(
        features=features,
        cfg=BirthCurriculumConfig(),
        event_bus=bus,
        mode="sim",
    )
    decision = orch.evaluate_dynamic_wall(
        correlation_id="c2",
        stage="STAGE1_TREND",
        stage_trades=100,
        required=100,
        apply=False,
    )
    assert decision.proposal
    assert decision.gate is not None
    assert decision.gate.allowed is True
    assert decision.applied is False
    assert len(bus.history("birth.phase2.wall.proposal", limit=5)) >= 1
    assert len(bus.history("birth.phase2.gate.result", limit=5)) >= 1


@pytest.mark.unit
def test_apply_param_with_twin() -> None:
    features = Phase2AutonomyFeatures(
        enabled=True,
        self_adaptive_params_enabled=True,
        require_perfect_birth_flag=False,
        require_twin_for_apply=True,
        execution_mode="apply",
    )
    state = WallAdaptationState(effective_winrate_window=12, effective_reward_window=12)
    orch = Phase2AutonomyOrchestrator(
        features=features,
        cfg=BirthCurriculumConfig(),
        approval_twin=_FakeTwin(),
        mode="sim",
    )
    decision = orch.evaluate_param_adjustment(
        stage="STAGE1_TREND",
        learning_health="declining",
        current_winrate_window=12,
        current_reward_window=12,
        post_volume_gate=True,
        wall_state=state,
        apply=True,
    )
    assert decision.gate is not None
    assert decision.gate.allowed is True
    assert decision.applied is True


@pytest.mark.unit
def test_instance_adapt_apply_payload() -> None:
    features = Phase2AutonomyFeatures(
        enabled=True,
        instance_adapt_enabled=True,
        require_perfect_birth_flag=False,
        require_twin_for_apply=False,
        execution_mode="apply",
    )
    orch = Phase2AutonomyOrchestrator(features=features, mode="sim")
    decision = orch.evaluate_instance_adapt(
        adaptation_tier=2,
        retries_this_stage=2,
        apply=True,
    )
    assert decision.applied is True
    assert decision.apply_payload.get("os_spawn") is False
    assert decision.apply_payload.get("process_restart_required") is False
