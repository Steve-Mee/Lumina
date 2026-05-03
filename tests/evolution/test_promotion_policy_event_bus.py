from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration import EventBus
from lumina_core.container import ApplicationContainer
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator
from lumina_core.evolution.promotion_gate import PromotionGate, PromotionGateEvidence
from lumina_core.evolution.promotion_policy import PromotionPolicy


def _base_evidence() -> PromotionGateEvidence:
    return PromotionGateEvidence(
        dna_hash="dna_1234567890",
        cv_combinatorial={
            "combinations": 8,
            "mean_oos_sharpe": 0.8,
            "sharpe_positive_pct": 0.75,
            "pbo": 0.2,
            "dsr": 0.35,
        },
        cv_walk_forward={"windows": 8, "sharpe_positive_pct": 0.75},
        reality_gap_stats={"band_status": "YELLOW", "gap_trend": "STABLE", "mean_gap": 0.35},
        stress_report={"stress_ready_for_real_gate": True, "worst_case_drawdown": 2000.0},
        live_pnl_samples=[5.0 + (i * 0.02) for i in range(40)],
        backtest_pnl_samples=[4.0 + (i * 0.01) for i in range(40)],
        min_sample_trades=30,
        starting_equity=50_000.0,
        backtest_fill_rate=0.95,
        live_fill_rate=0.85,
        backtest_slippage=0.8,
        live_slippage=0.95,
    )


@pytest.mark.unit
def test_publish_promotion_gate_violation_to_event_bus() -> None:
    # gegeven
    event_bus = EventBus()
    policy = PromotionPolicy(owner=SimpleNamespace(), event_bus=event_bus)
    gate = PromotionGate()
    decision = gate.evaluate(
        "dna_1234567890",
        evidence=_base_evidence().model_copy(
            update={
                "reality_gap_stats": {"band_status": "RED", "gap_trend": "WIDENING", "mean_gap": 1.25},
                "live_fill_rate": 0.45,
            }
        ),
    )

    # wanneer
    policy._publish_promotion_gate_violation(dna_hash="dna_1234567890", decision=decision)

    # dan
    events = event_bus.history("safety.constitution.violation", limit=5)
    assert len(events) == 1
    assert events[0].producer == "evolution.promotion_policy"
    assert events[0].payload["principle_name"] == "promotion_gate_failed"
    assert events[0].payload["dna_hash"] == "dna_1234567890"
    assert events[0].metadata["gate"] == "promotion_gate"


@pytest.mark.unit
def test_publish_violation_without_event_bus_is_noop() -> None:
    # gegeven
    policy = PromotionPolicy(owner=SimpleNamespace(), event_bus=None)
    decision = PromotionGate().evaluate(
        "dna_1234567890",
        evidence=_base_evidence().model_copy(
            update={"reality_gap_stats": {"band_status": "RED", "gap_trend": "WIDENING", "mean_gap": 1.25}}
        ),
    )

    # wanneer / dan
    policy._publish_promotion_gate_violation(dna_hash="dna_1234567890", decision=decision)


@pytest.mark.unit
def test_orchestrator_bind_promotion_event_bus_updates_policy_dependency() -> None:
    # gegeven
    orchestrator = object.__new__(EvolutionOrchestrator)
    bus = EventBus()

    # wanneer
    orchestrator.bind_promotion_event_bus(bus)

    # dan
    assert isinstance(orchestrator._promotion_policy, PromotionPolicy)
    assert orchestrator._promotion_policy._event_bus is bus


@pytest.mark.unit
def test_run_shadow_validation_gate_publishes_violation_when_gate_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # gegeven
    event_bus = EventBus()
    owner = SimpleNamespace(
        _guard=SimpleNamespace(shadow_validation_passed=lambda **_: True),
        _approval_twin=SimpleNamespace(
            evaluate_shadow_promotion=lambda **_: {
                "recommendation": True,
                "confidence": 0.99,
                "risk_flags": [],
                "explanation": "ok",
            }
        ),
        _promotion_gate=SimpleNamespace(evaluate=lambda **_: (_ for _ in ()).throw(RuntimeError("gate failed"))),
        _veto_registry=None,
        _telegram_notifier=SimpleNamespace(poll_for_replies=lambda: None, is_vetoed_or_expired=lambda _dna: False),
        _notification_scheduler=SimpleNamespace(schedule_notification=lambda **_: None),
    )
    policy = PromotionPolicy(owner=owner, event_bus=event_bus)
    dna = PolicyDNA(
        prompt_id="p1",
        version="v1",
        hash="dna_1234567890",
        content="{}",
        fitness_score=1.0,
        generation=1,
    )
    monkeypatch.setattr(
        policy,
        "load_shadow_runs",
        lambda: {
            dna.hash: {
                "dna_hash": dna.hash,
                "lineage_hash": dna.lineage_hash,
                "status": "pending",
                "target_days": 1,
                "daily_pnl": [10.0],
                "daily_fill_count": [1],
                "shadow_total_pnl": 10.0,
            }
        },
    )
    monkeypatch.setattr(policy, "save_shadow_runs", lambda _payload: None)
    monkeypatch.setattr(policy, "_build_promotion_evidence", lambda **_: _base_evidence())

    # wanneer
    result = policy.run_shadow_validation_gate(
        dna=dna,
        winner_fitness=1.0,
        nightly_report={},
        signed=True,
        generation_ok=True,
        shadow_runner=SimpleNamespace(),
    )

    # dan
    assert result["promote_now"] is False
    events = event_bus.history("safety.constitution.violation", limit=5)
    assert len(events) == 1
    assert events[0].payload["principle_name"] == "promotion_gate_failed"
    assert events[0].payload["dna_hash"] == dna.hash
    assert "evidence_unavailable" in events[0].payload["detail"]


@pytest.mark.unit
def test_container_binding_wires_orchestrator_promotion_policy_event_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    # gegeven
    captured: dict[str, object | None] = {"bus": None, "market_data_service": None}

    class _StubOrchestrator:
        def bind_promotion_event_bus(self, event_bus: EventBus | None) -> None:
            captured["bus"] = event_bus

        def bind_market_data_service(self, market_data_service: object | None) -> None:
            captured["market_data_service"] = market_data_service

    import lumina_core.evolution.evolution_orchestrator as evolution_orchestrator_module

    monkeypatch.setattr(evolution_orchestrator_module, "EvolutionOrchestrator", _StubOrchestrator)
    container = object.__new__(ApplicationContainer)
    container.event_bus = EventBus()
    container.market_data_service = object()

    # wanneer
    container._bind_evolution_promotion_event_bus()

    # dan
    assert captured["bus"] is container.event_bus
    assert captured["market_data_service"] is container.market_data_service


@pytest.mark.unit
def test_orchestrator_bind_market_data_service_rebuilds_sim_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    # gegeven
    orchestrator = object.__new__(EvolutionOrchestrator)
    orchestrator._market_data_service = None
    calls: list[object | None] = []

    def _stub_create() -> str:
        calls.append(orchestrator._market_data_service)
        return "stub-sim-runner"

    monkeypatch.setattr(orchestrator, "_create_sim_runner", _stub_create)
    market_data_service = object()

    # wanneer
    orchestrator.bind_market_data_service(market_data_service)

    # dan
    assert orchestrator._market_data_service is market_data_service
    assert getattr(orchestrator, "_sim_runner") == "stub-sim-runner"
    assert calls == [market_data_service]


@pytest.mark.unit
def test_promotion_gate_violation_publication_is_deterministic() -> None:
    # gegeven
    event_bus = EventBus()
    policy = PromotionPolicy(owner=SimpleNamespace(), event_bus=event_bus)
    gate = PromotionGate()
    decision = gate.evaluate(
        "dna_1234567890",
        evidence=_base_evidence().model_copy(
            update={
                "reality_gap_stats": {"band_status": "RED", "gap_trend": "WIDENING", "mean_gap": 1.25},
                "live_fill_rate": 0.45,
            }
        ),
    )

    # wanneer
    policy._publish_promotion_gate_violation(dna_hash="dna_1234567890", decision=decision)
    policy._publish_promotion_gate_violation(dna_hash="dna_1234567890", decision=decision)

    # dan
    events = event_bus.history("safety.constitution.violation", limit=10)
    assert len(events) == 2
    assert events[0].payload == events[1].payload
    assert events[0].metadata["dna_hash"] == events[1].metadata["dna_hash"]
    assert events[0].metadata["gate"] == events[1].metadata["gate"]
    assert int(events[0].metadata["sequence"]) + 1 == int(events[1].metadata["sequence"])
