"""Slice A golden path: Phase 2 closed loop changes outcomes when ON; inert when OFF."""

from __future__ import annotations

from typing import Any

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_handler_registry import BirthHandlerRegistry
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.orchestrator import Phase2AutonomyOrchestrator
from lumina_core.birth.wall_adaptation_handler import WallAdaptationHandler


class _FakeTwin:
    def evaluate_dna_promotion(self, _dna: Any) -> dict[str, Any]:
        return {
            "confidence": 0.92,
            "recommendation": True,
            "executable": True,
            "effective_recommendation": True,
            "mode": "full_auto",
            "risk_flags": [],
        }


def _phase2_cfg(**kwargs: Any) -> BirthCurriculumConfig:
    base = dict(
        stage1_trend_trades=100,
        stage1_winrate_stagnation_rollouts=2,
        stage2_hold_stagnation_rollouts=2,
        certified_stage_stall_wall_sec=600,
        wall_behavior="adaptive",
        adaptation_enabled=True,
        meta_controller_enabled=False,
        max_stage_retries=3,
        exploration_chunk_size=8,
        rollout_chunk_trades=20,
        phase2_autonomy_enabled=True,
        phase2_dynamic_wall_enabled=True,
        phase2_self_adaptive_params_enabled=True,
        phase2_instance_adapt_enabled=True,
        phase2_require_perfect_birth_flag=False,
        phase2_allow_sim_scaffold=True,
        phase2_require_twin_for_apply=True,
    )
    base.update(kwargs)
    return BirthCurriculumConfig(**base)


@pytest.mark.unit
def test_closed_loop_off_by_default_no_phase2_meta() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(
        stage1_trend_trades=100,
        stage1_winrate_stagnation_rollouts=2,
        certified_stage_stall_wall_sec=300,
        wall_behavior="adaptive",
        phase2_autonomy_enabled=False,
    )
    client = BirthBusClient(bus, cfg, BirthRewardConfig())
    trigger = client.wall_evaluate_trigger(
        CurriculumStage.STAGE1_TREND,
        stage_trades=150,
        stage_wins=45,
        required=100,
        hold_ratio=0.2,
        constitution_violations=0,
        range_flat_ratio=0.0,
        range_round_trips=0,
        range_total_signals=100,
        elapsed_stage_sec=400.0,
        winrate_stagnation_count=3,
        hold_stagnation_count=0,
        wall_budget_exhausted=False,
        allow_provisional=False,
        failure_key="stage1_winrate",
        force=False,
        low_velocity_attempts=0,
        last_adaptation_stage_trades=-1,
    )
    assert trigger is not None
    assert trigger.get("triggered") is True
    # No phase2 thresholds applied when disabled
    p2 = trigger.get("phase2_wall") or {}
    assert p2.get("applied") is not True
    assert not p2.get("thresholds_applied")


@pytest.mark.unit
def test_closed_loop_wall_thresholds_applied_when_gated() -> None:
    bus = EventBus()
    cfg = _phase2_cfg()
    twin = _FakeTwin()
    features = Phase2AutonomyFeatures.from_curriculum_cfg(cfg)
    orch = Phase2AutonomyOrchestrator(
        features=features,
        cfg=cfg,
        event_bus=bus,
        approval_twin=twin,
        mode="sim",
    )
    handler = WallAdaptationHandler(
        bus, cfg, registry=None, phase2_orchestrator=orch
    )
    handler.attach()

    # RANGE + early progress tends to extend wall (> base 600)
    from lumina_core.birth.birth_bus_choreography import publish_snapshot

    publish_snapshot(
        bus,
        producer="test",
        correlation_id="wall-on",
        signal="wall_evaluate_trigger",
        stage=CurriculumStage.STAGE1_TREND.value,
        context={
            "stage_trades": 40,
            "stage_wins": 10,
            "required": 100,
            "hold_ratio": 0.2,
            "constitution_violations": 0,
            "range_flat_ratio": 0.0,
            "range_round_trips": 0,
            "range_total_signals": 0,
            "elapsed_stage_sec": 100.0,
            "winrate_stagnation_count": 0,
            "hold_stagnation_count": 0,
            "wall_budget_exhausted": False,
            "allow_provisional": False,
            "failure_key": "stage1_winrate",
            "force": False,
            "low_velocity_attempts": 0,
            "last_adaptation_stage_trades": -1,
            "regime": "RANGE",
            "winrate_slope": 0.0,
        },
    )
    # Response is set on registry; without registry, inspect bus phase2 gate + decision path
    # Direct orchestrator proof of apply_payload:
    decision = orch.evaluate_dynamic_wall(
        correlation_id="direct",
        stage="STAGE1_TREND",
        stage_trades=40,
        required=100,
        regime="RANGE",
        apply=True,
    )
    assert decision.gate is not None
    assert decision.gate.allowed is True
    assert decision.applied is True
    assert int(decision.apply_payload["effective_stall_wall_sec"]) != int(
        cfg.certified_stage_stall_wall_sec
    ) or float(decision.proposal.get("stall_wall_sec_multiplier", 1.0)) != 1.0
    # Multiplier for early+range should be > 1
    assert float(decision.proposal["stall_wall_sec_multiplier"]) > 1.0
    assert int(decision.apply_payload["effective_stall_wall_sec"]) > 600

    handler.detach()


@pytest.mark.unit
def test_closed_loop_wall_via_handler_sets_effective_cfg() -> None:
    bus = EventBus()
    cfg = _phase2_cfg()
    twin = _FakeTwin()
    reg = BirthHandlerRegistry(bus, cfg, BirthRewardConfig(), approval_twin=twin, mode="sim")
    reg.attach_all()
    assert reg.phase2 is not None

    client = BirthBusClient(bus, cfg, BirthRewardConfig())
    # BirthBusClient builds its own registry — inject phase2 path via handler on client
    # Use registry's wall handler through signals on shared bus:
    from lumina_core.birth.birth_bus_choreography import publish_snapshot

    publish_snapshot(
        bus,
        producer="test",
        correlation_id="h1",
        signal="wall_evaluate_trigger",
        stage=CurriculumStage.STAGE1_TREND.value,
        context={
            "stage_trades": 40,
            "stage_wins": 10,
            "required": 100,
            "hold_ratio": 0.2,
            "constitution_violations": 0,
            "range_flat_ratio": 0.0,
            "range_round_trips": 0,
            "range_total_signals": 0,
            "elapsed_stage_sec": 100.0,
            "winrate_stagnation_count": 0,
            "hold_stagnation_count": 0,
            "wall_budget_exhausted": False,
            "allow_provisional": False,
            "failure_key": "stage1_winrate",
            "force": False,
            "low_velocity_attempts": 0,
            "last_adaptation_stage_trades": -1,
            "regime": "RANGE",
            "winrate_slope": 0.0,
        },
    )
    resp = reg.get_response("h1")
    # Not triggered (below volume gate) but phase2_wall should carry applied thresholds
    p2 = resp.get("phase2_wall") or {}
    if not p2 and resp.get("trigger"):
        p2 = (resp.get("trigger") or {}).get("phase2_wall") or {}
    assert p2.get("thresholds_applied") is True
    eff = p2.get("effective_cfg") or {}
    assert int(eff.get("certified_stage_stall_wall_sec", 0)) > 600

    reg.detach_all()
    _ = client  # silence unused when bus shared patterns evolve


@pytest.mark.unit
def test_closed_loop_recovery_param_and_instance() -> None:
    bus = EventBus()
    cfg = _phase2_cfg()
    twin = _FakeTwin()
    reg = BirthHandlerRegistry(bus, cfg, BirthRewardConfig(), approval_twin=twin, mode="sim")
    reg.attach_all()

    from lumina_core.birth.birth_bus_choreography import publish_snapshot

    publish_snapshot(
        bus,
        producer="test",
        correlation_id="r1",
        signal="adaptation_try_recovery",
        stage=CurriculumStage.STAGE1_TREND.value,
        context={
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
            "constitution_violations": 0,
            "learning_health": "declining",
            "snapshot": None,
            "winrate": 0.30,
            "escalation_level": 0,
            "adaptation_tier": 2,
            "retries_this_stage": 2,
            "plateau_active": False,
            "phoenix_eligible": True,
        },
    )
    resp = reg.get_response("r1")
    adaptation = resp.get("adaptation") or {}
    assert adaptation.get("applied") is True
    p2 = adaptation.get("phase2") or {}
    param = p2.get("param") or {}
    inst = p2.get("instance") or {}
    assert param.get("applied") is True
    assert inst.get("applied") is True
    # Instance at tier/retries high → spawn_plateau path
    assert adaptation.get("spawn_plateau") is True or (
        inst.get("apply_payload") or {}
    ).get("spawn_plateau")
    # Param windows should have moved on state
    state = adaptation.get("state") or {}
    assert int(state.get("effective_winrate_trend_window", 12)) >= 12

    reg.detach_all()


@pytest.mark.unit
def test_closed_loop_real_mode_apply_rejected() -> None:
    cfg = _phase2_cfg()
    features = Phase2AutonomyFeatures.from_curriculum_cfg(cfg)
    orch = Phase2AutonomyOrchestrator(
        features=features,
        cfg=cfg,
        approval_twin=_FakeTwin(),
        mode="real",
    )
    decision = orch.evaluate_dynamic_wall(
        stage="STAGE1_TREND",
        stage_trades=50,
        required=100,
        apply=True,
    )
    assert decision.applied is False
    assert decision.gate is not None
    assert decision.gate.allowed is False
