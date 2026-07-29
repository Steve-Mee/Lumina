"""Organism Autonomy Engine tests."""

from __future__ import annotations

import pytest

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.death_spiral_guard import (
    DeathSpiralState,
    record_stall_signature,
    reset_after_novelty,
)
from lumina_core.birth.organism_autonomy import (
    OrganismAutonomyState,
    RecoveryDispatch,
    evaluate_terminal_stall,
    map_recommended_to_service_action,
)
from lumina_core.birth.phoenix_loop import (
    PHOENIX_CYCLE_REASON,
    PhoenixLoopState,
    select_phoenix_novelty,
)


def _cfg(**overrides: object) -> BirthCurriculumConfig:
    base = dict(
        autonomous_recovery_enabled=True,
        phoenix_loop_enabled=True,
        phoenix_max_cycles=12,
        allow_provisional_pass=True,
        graduation_mode="evolution_deferred",
        provisional_oos_floor=0.35,
        stage1_winrate_pass_floor=0.35,
        death_spiral_repeat_threshold=3,
        death_spiral_novelty_budget=2,
    )
    base.update(overrides)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_map_recommended_actions() -> None:
    assert map_recommended_to_service_action("expand_data") == "expand_and_retry"
    assert map_recommended_to_service_action("phoenix_reset") == "phoenix_recovery"
    assert map_recommended_to_service_action("unknown") == "resume_stalled_stage"


@pytest.mark.unit
def test_phoenix_cycle_selects_novelty() -> None:
    state = PhoenixLoopState(phoenix_count=2)
    novelty = select_phoenix_novelty(state, cfg=_cfg())
    assert novelty.value in {"expand_data", "policy_swarm", "reward_sweep", "soft_gate", "widen_horizon"}


@pytest.mark.unit
def test_death_spiral_circuit_breaker() -> None:
    state = DeathSpiralState()
    cfg = _cfg(death_spiral_repeat_threshold=2)
    assert record_stall_signature(
        state,
        curriculum_stage="stage1_trend",
        blocker_metric="trend_winrate",
        blocker_value=0.41,
        cfg=cfg,
    ) is False
    tripped = record_stall_signature(
        state,
        curriculum_stage="stage1_trend",
        blocker_metric="trend_winrate",
        blocker_value=0.41,
        cfg=cfg,
    )
    assert tripped is True
    reset_after_novelty(state, cfg=cfg)
    assert state.circuit_breaker_tripped is False


@pytest.mark.unit
def test_evaluate_terminal_stall_phoenix_resume() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(),
        autonomy_state=autonomy,
        pending={
            "terminal_stall_reason": "stall_remediation_exhausted",
            "blocker_metric": "trend_winrate",
            "blocker_value": 0.39,
        },
        curriculum_stage="stage1_trend",
        stage_trades=500,
        required=600,
        constitution_violations=0,
        fitness_signal=0.38,
        remediation_cycles_exhausted=True,
        plateau_exhausted=True,
    )
    assert decision.dispatch == RecoveryDispatch.PHOENIX_RESUME
    assert decision.needs_attention is False
    assert decision.retryable is True
    assert decision.stall_reason == PHOENIX_CYCLE_REASON


@pytest.mark.unit
def test_evaluate_terminal_stall_no_lift_brake_blocks_phoenix() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(),
        autonomy_state=autonomy,
        pending={
            "terminal_stall_reason": "plateau_evolution_exhausted",
            "blocker_metric": "winrate",
            "blocker_value": 0.368,
        },
        curriculum_stage="stage1_trend",
        stage_trades=2700,
        required=200,
        constitution_violations=0,
        fitness_signal=0.368,
        remediation_cycles_exhausted=True,
        plateau_exhausted=True,
        recovery_no_lift_brake=True,
        swarm_tournament_resolved=False,
    )
    assert decision.dispatch == RecoveryDispatch.TERMINAL_NOTIFY_ONLY
    assert decision.needs_attention is True
    assert decision.retryable is True
    assert "best-winrate lift" in decision.message


@pytest.mark.unit
def test_evaluate_terminal_stall_no_lift_brake_skipped_when_swarm_resolved() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(phoenix_loop_enabled=False, allow_provisional_pass=False),
        autonomy_state=autonomy,
        pending={
            "terminal_stall_reason": "plateau_evolution_exhausted",
            "blocker_metric": "winrate",
            "blocker_value": 0.368,
        },
        curriculum_stage="stage1_trend",
        stage_trades=2700,
        required=200,
        constitution_violations=0,
        fitness_signal=0.368,
        remediation_cycles_exhausted=True,
        plateau_exhausted=True,
        recovery_no_lift_brake=True,
        swarm_tournament_resolved=True,
        recommended_recovery_action="expand_data",
    )
    # Brake must not short-circuit to operator attention when swarm is CONTINUE-resolved.
    assert decision.dispatch != RecoveryDispatch.TERMINAL_NOTIFY_ONLY or (
        "best-winrate lift" not in decision.message
    )
    assert "best-winrate lift" not in decision.message
    assert decision.dispatch == RecoveryDispatch.CONTINUE_LOOP


@pytest.mark.unit
def test_evaluate_terminal_stall_disabled_needs_attention() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(autonomous_recovery_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stall_remediation_exhausted"},
        curriculum_stage="stage1_trend",
        stage_trades=100,
        required=200,
        constitution_violations=0,
        fitness_signal=0.2,
    )
    assert decision.dispatch == RecoveryDispatch.TERMINAL_NOTIFY_ONLY
    assert decision.needs_attention is True


@pytest.mark.unit
def test_evaluate_terminal_stall_provisional_graduate() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "plateau_evolution_exhausted"},
        curriculum_stage="stage1_trend",
        stage_trades=600,
        required=500,
        constitution_violations=0,
        fitness_signal=0.40,
        plateau_exhausted=True,
    )
    assert decision.dispatch == RecoveryDispatch.PROVISIONAL_GRADUATE
    assert "provisional" in decision.message.lower()


@pytest.mark.unit
def test_evaluate_terminal_stall_continue_loop_with_recommended_action() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(phoenix_loop_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stage_stalled"},
        curriculum_stage="stage1_trend",
        stage_trades=200,
        required=500,
        constitution_violations=0,
        fitness_signal=0.30,
        recommended_recovery_action="expand_data",
    )
    assert decision.dispatch == RecoveryDispatch.CONTINUE_LOOP
    assert decision.recommended_action == "expand_and_retry"
    assert autonomy.autonomous_recovery_count == 1


@pytest.mark.unit
def test_organism_autonomy_state_metrics_roundtrip() -> None:
    original = OrganismAutonomyState(
        phoenix=PhoenixLoopState(phoenix_count=2),
        death_spiral=DeathSpiralState(),
        last_recommended_action="expand_data",
        autonomous_recovery_count=5,
    )
    metrics = original.to_metrics()
    restored = OrganismAutonomyState.from_metrics(metrics)
    assert restored.autonomous_recovery_count == 5
    assert restored.last_recommended_action == "expand_data"
    assert restored.phoenix.phoenix_count == 2


@pytest.mark.unit
def test_organism_autonomy_state_from_metrics_empty() -> None:
    restored = OrganismAutonomyState.from_metrics(None)
    assert restored.autonomous_recovery_count == 0
    assert restored.phoenix.phoenix_count == 0


class _TwinStub:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.sync_calls = 0

    def sync_mode_from_controller(self) -> str:
        self.sync_calls += 1
        return str(self.payload.get("mode") or "shadow")

    def evaluate_dna_promotion(self, _dna: object) -> dict[str, object]:
        self.calls += 1
        return self.payload


@pytest.mark.unit
def test_evaluate_terminal_stall_twin_high_conf_approval() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    twin = _TwinStub(
        {
            "confidence": 0.92,
            "recommendation": True,
            "effective_recommendation": True,
            "executable": True,
            "mode": "full_auto",
            "risk_flags": [],
        }
    )
    decision = evaluate_terminal_stall(
        cfg=_cfg(phoenix_loop_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stage_stalled", "blocker_metric": "trend_winrate", "blocker_value": 0.4},
        curriculum_stage="stage1_trend",
        approval_twin=twin,
        stage_trades=200,
        required=500,
        constitution_violations=0,
        fitness_signal=0.30,
        recommended_recovery_action="expand_data",
        swarm_tournament_resolved=True,
    )
    assert decision.dispatch == RecoveryDispatch.CONTINUE_LOOP
    assert "Twin high-conf autonomous approval" in decision.message
    assert twin.calls == 1
    assert twin.sync_calls == 1
    assert autonomy.autonomous_recovery_count == 1


@pytest.mark.unit
def test_evaluate_terminal_stall_twin_full_auto_blocked_until_swarm_resolved() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    twin = _TwinStub(
        {
            "confidence": 0.92,
            "recommendation": True,
            "effective_recommendation": True,
            "executable": True,
            "mode": "full_auto",
            "risk_flags": [],
        }
    )
    decision = evaluate_terminal_stall(
        cfg=_cfg(phoenix_loop_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stage_stalled", "blocker_metric": "trend_winrate", "blocker_value": 0.4},
        curriculum_stage="stage1_trend",
        approval_twin=twin,
        stage_trades=200,
        required=500,
        constitution_violations=0,
        fitness_signal=0.30,
        recommended_recovery_action="expand_data",
        swarm_tournament_resolved=False,
    )
    assert "Twin high-conf autonomous approval" not in decision.message
    assert decision.dispatch == RecoveryDispatch.CONTINUE_LOOP
    assert decision.recommended_action == "expand_and_retry"


@pytest.mark.unit
def test_evaluate_terminal_stall_shadow_mode_twin_does_not_sole_auto() -> None:
    """Shadow mode proposes but does not execute CONTINUE from twin alone."""
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    twin = _TwinStub(
        {
            "confidence": 0.95,
            "recommendation": True,
            "effective_recommendation": False,
            "executable": False,
            "mode": "shadow",
            "risk_flags": [],
        }
    )
    decision = evaluate_terminal_stall(
        cfg=_cfg(phoenix_loop_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stage_stalled", "blocker_metric": "trend_winrate", "blocker_value": 0.4},
        curriculum_stage="stage1_trend",
        approval_twin=twin,
        stage_trades=200,
        required=500,
        constitution_violations=0,
        fitness_signal=0.30,
        recommended_recovery_action="expand_data",
    )
    # Falls through to non-twin recovery path (recommended action), not twin auto message
    assert decision.dispatch == RecoveryDispatch.CONTINUE_LOOP
    assert "Twin high-conf autonomous approval" not in decision.message
    assert decision.recommended_action == "expand_and_retry"


@pytest.mark.unit
def test_evaluate_terminal_stall_twin_high_conf_veto() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    twin = _TwinStub(
        {
            "confidence": 0.95,
            "recommendation": False,
            "effective_recommendation": False,
            "executable": False,
            "mode": "assisted",
            "risk_flags": [],
        }
    )
    decision = evaluate_terminal_stall(
        cfg=_cfg(phoenix_loop_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stage_stalled", "blocker_metric": "trend_winrate", "blocker_value": 0.4},
        curriculum_stage="stage1_trend",
        approval_twin=twin,
        stage_trades=200,
        required=500,
        constitution_violations=0,
        fitness_signal=0.30,
    )
    assert decision.dispatch == RecoveryDispatch.TERMINAL_NOTIFY_ONLY
    assert decision.needs_attention is True
    assert "Twin high-conf veto" in decision.message


@pytest.mark.unit
def test_evaluate_terminal_stall_twin_subordinates_constitution_violations() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    twin = _TwinStub({"confidence": 0.95, "recommendation": True, "risk_flags": []})
    decision = evaluate_terminal_stall(
        cfg=_cfg(phoenix_loop_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stage_stalled", "blocker_metric": "trend_winrate", "blocker_value": 0.4},
        curriculum_stage="stage1_trend",
        approval_twin=twin,
        stage_trades=200,
        required=500,
        constitution_violations=2,
        fitness_signal=0.30,
        recommended_recovery_action="expand_data",
    )
    assert decision.dispatch == RecoveryDispatch.CONTINUE_LOOP
    assert decision.recommended_action == "expand_and_retry"


@pytest.mark.unit
def test_evaluate_terminal_stall_disabled_returns_notify_only_with_twin_present() -> None:
    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    twin = _TwinStub({"confidence": 0.5, "recommendation": True, "risk_flags": []})
    decision = evaluate_terminal_stall(
        cfg=_cfg(autonomous_recovery_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stage_stalled"},
        curriculum_stage="stage1_trend",
        approval_twin=twin,
        stage_trades=100,
        required=200,
        constitution_violations=0,
        fitness_signal=0.2,
    )
    assert decision.dispatch == RecoveryDispatch.TERMINAL_NOTIFY_ONLY
    assert decision.needs_attention is True


@pytest.mark.unit
def test_evaluate_terminal_stall_twin_error_falls_through_to_recommended() -> None:
    class _BrokenTwin:
        def evaluate_dna_promotion(self, _dna: object) -> dict[str, object]:
            raise RuntimeError("twin offline")

    autonomy = OrganismAutonomyState(phoenix=PhoenixLoopState(), death_spiral=DeathSpiralState())
    decision = evaluate_terminal_stall(
        cfg=_cfg(phoenix_loop_enabled=False),
        autonomy_state=autonomy,
        pending={"terminal_stall_reason": "stage_stalled", "blocker_metric": "trend_winrate", "blocker_value": 0.4},
        curriculum_stage="stage1_trend",
        approval_twin=_BrokenTwin(),
        stage_trades=200,
        required=500,
        constitution_violations=0,
        fitness_signal=0.30,
        recommended_recovery_action="phoenix_reset",
    )
    assert decision.dispatch == RecoveryDispatch.CONTINUE_LOOP
    assert decision.recommended_action == "phoenix_recovery"


@pytest.mark.unit
def test_organism_autonomy_handler_passes_twin_on_bus() -> None:
    """Birth bus path must inject approval_twin (was dropped before ADR-0031 finish)."""
    from lumina_core.agent_orchestration.event_bus import EventBus
    from lumina_core.birth.birth_bus_client import BirthBusClient
    from lumina_core.birth.config import BirthRewardConfig
    from lumina_core.birth.curriculum import CurriculumStage

    twin = _TwinStub({"confidence": 0.91, "recommendation": True, "risk_flags": []})
    bus = EventBus()
    client = BirthBusClient(
        bus,
        _cfg(phoenix_loop_enabled=False),
        BirthRewardConfig(),
        approval_twin=twin,
    )
    assert client.registry.autonomy.approval_twin is twin
    assert client.registry.meta.approval_twin is twin
    assert client.registry.meta.controller.approval_twin is twin

    decision = client.autonomy_evaluate_terminal_stall(
        CurriculumStage.STAGE1_TREND,
        pending={"terminal_stall_reason": "stage_stalled", "blocker_metric": "trend_winrate", "blocker_value": 0.4},
        stage_trades=200,
        required=500,
        constitution_violations=0,
        fitness_signal=0.30,
        recommended_recovery_action="expand_data",
    )
    assert twin.calls >= 1
    assert decision.dispatch == RecoveryDispatch.CONTINUE_LOOP
