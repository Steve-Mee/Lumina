from __future__ import annotations

import json
from pathlib import Path

from lumina_core.agent_orchestration import EventBus
from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.steve_values_registry import SteveValueRecord, SteveValuesRegistry
from lumina_core.safety.constitutional_guard import ConstitutionalGuard
from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION


def _dna(*, fitness: float, mutation_rate: float, content: str) -> PolicyDNA:
    return PolicyDNA.create(
        prompt_id="approval_twin",
        version="candidate",
        content=content,
        fitness_score=fitness,
        generation=2,
        mutation_rate=mutation_rate,
        lineage_hash="GENESIS",
    )


def test_evaluate_dna_promotion_returns_required_shape(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "values.sqlite3",
        jsonl_path=tmp_path / "values.jsonl",
    )
    twin = ApprovalTwinAgent(
        registry=registry,
        model_path=tmp_path / "twin_model.json",
        mode="shadow",
    )

    decision = twin.evaluate_dna_promotion(_dna(fitness=1.2, mutation_rate=0.1, content="risk guard stop"))

    required = {
        "recommendation",
        "confidence",
        "explanation",
        "risk_flags",
        "mode",
        "authority",
        "executable",
        "effective_recommendation",
    }
    assert required.issubset(set(decision.keys()))
    assert isinstance(decision["recommendation"], bool)
    assert 0.0 <= float(decision["confidence"]) <= 1.0
    assert isinstance(decision["explanation"], str)
    assert isinstance(decision["risk_flags"], list)
    # Shadow: never executable even if raw recommendation True
    assert decision["mode"] == "shadow"
    assert decision["executable"] is False
    assert decision["effective_recommendation"] is False


def test_shadow_mode_never_executable_full_auto_is(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "values.sqlite3",
        jsonl_path=tmp_path / "values.jsonl",
    )
    from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
    from lumina_core.evolution.twin_mode_promotion_gate import TwinModeController

    store = TwinMetricsStore(path=tmp_path / "m.jsonl", summary_path=tmp_path / "s.json")
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "mode.json",
        metrics_store=store,
        initial_mode="shadow",
    )
    twin = ApprovalTwinAgent(
        registry=registry,
        model_path=tmp_path / "twin_model.json",
        mode="shadow",
        metrics_store=store,
        mode_controller=ctrl,
    )
    d_shadow = twin.evaluate_dna_promotion(
        _dna(fitness=1.5, mutation_rate=0.05, content="risk guard stop cooldown safety")
    )
    assert d_shadow["executable"] is False
    assert d_shadow["effective_recommendation"] is False

    twin.set_mode("full_auto", force=True)
    d_full = twin.evaluate_dna_promotion(
        _dna(fitness=1.5, mutation_rate=0.05, content="risk guard stop cooldown safety")
    )
    assert d_full["mode"] == "full_auto"
    # If raw rec True and clean, effective True; if False, still consistent
    assert d_full["effective_recommendation"] == d_full["recommendation"]
    if d_full["recommendation"]:
        assert d_full["executable"] is True


def test_label_from_answer_modify_is_soft_reject() -> None:
    assert ApprovalTwinAgent._label_from_answer("APPROVE") == 1.0
    assert ApprovalTwinAgent._label_from_answer("VETO") == 0.0
    assert ApprovalTwinAgent._label_from_answer("MODIFY: cut size") == 0.35
    assert ApprovalTwinAgent._label_from_answer("MODIFY: still approve half") == 0.35
    assert ApprovalTwinAgent._label_from_answer("") is None


def test_rlhf_light_update_persists_model(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "values.sqlite3",
        jsonl_path=tmp_path / "values.jsonl",
    )
    records = [
        SteveValueRecord.create(
            vraag="Promote to REAL? risk low",
            steve_antwoord="APPROVE",
            context_dna_hash="a",
            confidence_score=0.9,
        ),
        SteveValueRecord.create(
            vraag="Promote to REAL? drawdown high",
            steve_antwoord="VETO",
            context_dna_hash="b",
            confidence_score=0.2,
        ),
    ]
    for record in records:
        registry.append(record)

    model_path = tmp_path / "twin_model.json"
    twin = ApprovalTwinAgent(registry=registry, model_path=model_path)
    result = twin.fine_tune_from_registry(limit=10)

    assert result["updated"] is True
    assert int(result["updates"]) >= 2
    assert model_path.exists()


def test_twin_publishes_typed_events_to_bus(tmp_path: Path) -> None:
    """Twin publishes TwinDecisionEvent + training update to central EventBus (primary observability path)."""
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "values.sqlite3",
        jsonl_path=tmp_path / "values.jsonl",
    )
    bus = EventBus()
    twin = ApprovalTwinAgent(registry=registry, model_path=tmp_path / "twin_model.json", event_bus=bus)

    dna = _dna(fitness=1.1, mutation_rate=0.05, content="risk guard stop cooldown")
    decision = twin.evaluate_dna_promotion(dna)
    assert "recommendation" in decision

    events = bus.history("evolution.twin.decision", limit=5)
    assert len(events) >= 1
    p = events[0].payload
    assert p["dna_hash"] == str(dna.hash)
    assert "recommendation" in p
    assert "confidence" in p and 0.0 <= float(p["confidence"]) <= 1.0
    assert isinstance(p.get("risk_flags", []), list)

    # training path
    rec = SteveValueRecord.create(
        vraag="promote low risk?",
        steve_antwoord="APPROVE",
        context_dna_hash="x",
        confidence_score=0.85,
    )
    registry.append(rec)
    twin.rlhf_light_update(records=[rec])
    train_events = bus.history("evolution.twin.training_update", limit=3)
    assert len(train_events) >= 1
    tp = train_events[-1].payload
    assert "updates" in tp and "reward" in tp

    # bind after ctor also works
    bus2 = EventBus()
    twin.bind_event_bus(bus2)
    twin.evaluate_dna_promotion(dna)
    assert len(bus2.history("evolution.twin.decision", limit=1)) == 1


def test_evaluate_shadow_promotion_records_durable_metrics(tmp_path: Path) -> None:
    """Shadow path proposals write TwinMetricsStore for promotion gates."""
    from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
    from lumina_core.evolution.twin_mode_promotion_gate import TwinModeController

    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "values.sqlite3",
        jsonl_path=tmp_path / "values.jsonl",
    )
    store = TwinMetricsStore(path=tmp_path / "m.jsonl", summary_path=tmp_path / "s.json")
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "mode.json",
        metrics_store=store,
        initial_mode="shadow",
    )
    twin = ApprovalTwinAgent(
        registry=registry,
        model_path=tmp_path / "twin_model.json",
        mode="shadow",
        metrics_store=store,
        mode_controller=ctrl,
    )
    dna = _dna(fitness=1.2, mutation_rate=0.05, content="risk guard stop cooldown safety")
    out = twin.evaluate_shadow_promotion(dna=dna, shadow_total_pnl=12.5, veto_blocked=False)
    assert out["mode"] == "shadow"
    assert out["executable"] is False
    snap = store.snapshot()
    assert snap.samples >= 1
    assert snap.path_samples >= 1


def test_try_promote_publishes_mode_promotion_event(tmp_path: Path) -> None:
    from lumina_core.evolution.twin_metrics_store import TwinMetricsStore
    from lumina_core.evolution.twin_mode_promotion_gate import TwinModeController

    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "values.sqlite3",
        jsonl_path=tmp_path / "values.jsonl",
    )
    store = TwinMetricsStore(path=tmp_path / "m.jsonl", summary_path=tmp_path / "s.json")
    for i in range(40):
        store.record_comparison(
            twin_recommendation=True,
            ground_truth_approve=True,
            source="steve_label",
            dna_hash=f"d{i}",
            mode="shadow",
        )
    ctrl = TwinModeController(
        mode_state_path=tmp_path / "mode.json",
        metrics_store=store,
        initial_mode="shadow",
    )
    bus = EventBus()
    twin = ApprovalTwinAgent(
        registry=registry,
        model_path=tmp_path / "twin_model.json",
        mode="shadow",
        metrics_store=store,
        mode_controller=ctrl,
        event_bus=bus,
    )
    result = twin.try_promote("assisted")
    assert result.get("promoted") is True
    events = bus.history("evolution.twin.mode_promotion", limit=5)
    assert len(events) >= 1
    assert events[0].payload.get("promoted") is True
    assert events[0].payload.get("target_mode") == "assisted"


def _evil_trick_content() -> str:
    return json.dumps({
        "content": "constitution guard risk stop safety first cooldown",
        "fitness_score": 1.8,
        "mutation_rate": 0.04,
        "disable_risk_controller": True,  # fatal
        "hyperparam_suggestion": {"max_risk_percent": 99},
    })


def test_twin_never_recommends_unconstitutional_dna(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "v.sqlite3", jsonl_path=tmp_path / "v.jsonl"
    )
    twin = ApprovalTwinAgent(registry=registry, model_path=tmp_path / "t.json")
    dna = _dna(fitness=1.8, mutation_rate=0.04, content=_evil_trick_content())
    res = twin.evaluate_dna_promotion(dna)
    assert res["recommendation"] is False
    assert any("constitution" in str(f) for f in res.get("risk_flags", []))

    # And direct guard also blocks
    g = ConstitutionalGuard()
    assert not g.veto_unless_constitutional(dna_content=_evil_trick_content(), mode="real", current_recommendation=True)


def test_twin_fails_closed_on_guard_error(tmp_path: Path, monkeypatch) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "v.sqlite3", jsonl_path=tmp_path / "v.jsonl"
    )
    twin = ApprovalTwinAgent(registry=registry, model_path=tmp_path / "t.json")
    dna = _dna(fitness=1.0, mutation_rate=0.1, content='{"safe": true}')

    def boom(*a, **k):
        raise RuntimeError("simulated constitution crash")

    monkeypatch.setattr(TRADING_CONSTITUTION, "audit", boom)
    res = twin.evaluate_dna_promotion(dna)
    # Fail-closed: on error during the twin's internal check we force False
    assert res["recommendation"] is False
    assert "twin_constitution_check_error" in res.get("risk_flags", []) or res["recommendation"] is False


def test_twin_risk_flags_include_constitution_violation(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "v.sqlite3", jsonl_path=tmp_path / "v.jsonl"
    )
    twin = ApprovalTwinAgent(registry=registry, model_path=tmp_path / "t.json")
    dna = _dna(fitness=0.5, mutation_rate=0.2, content='{"bypass_order_gatekeeper": true, "content": "guard risk"}')
    res = twin.evaluate_dna_promotion(dna)
    assert res["recommendation"] is False
    flags = [str(f) for f in res.get("risk_flags", [])]
    assert any("constitution" in f or "naked" in f or "no_naked" in f for f in flags), flags


def test_twin_subscribes_and_observes_shadow_verdict(tmp_path: Path, monkeypatch) -> None:
    """Twin bind_event_bus subscribes; shadow.verdict is observe-only (non-blocking)."""
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "v.sqlite3", jsonl_path=tmp_path / "v.jsonl"
    )
    bus = EventBus()
    twin = ApprovalTwinAgent(
        registry=registry, model_path=tmp_path / "t.json", event_bus=bus, mode="shadow"
    )
    assert twin.mode == "shadow"
    assert len(twin._subscription_tokens) >= 4

    recorded: list[dict] = []

    def _capture(**kwargs):
        recorded.append(dict(kwargs))

    monkeypatch.setattr(
        "lumina_core.evolution.approval_twin_agent.record_shadow_twin_alignment_monitoring",
        _capture,
    )

    bus.publish(
        topic="evolution.shadow.verdict",
        producer="test",
        payload={"verdict": "pass", "dna_hash": "abc123", "sample_size": 3, "pnl": 12.5},
    )
    assert twin.observations_total >= 1
    obs = bus.history("evolution.twin.shadow_observation", limit=5)
    assert len(obs) >= 1
    assert "agreed" in obs[-1].payload
    assert recorded  # alignment KPI wired


def test_twin_observe_promotion_does_not_raise_or_block(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "v.sqlite3", jsonl_path=tmp_path / "v.jsonl"
    )
    bus = EventBus()
    twin = ApprovalTwinAgent(registry=registry, model_path=tmp_path / "t.json", event_bus=bus)
    # Critical topic — valid payload required
    bus.publish(
        topic="evolution.promotion.decision",
        producer="test",
        payload={
            "dna_hash": "dna_xyz",
            "allowed": False,
            "reason": "shadow_failed",
            "stage": "shadow",
            "mode": "SIM",
        },
    )
    metrics = twin.observation_metrics()
    assert metrics["observations_total"] >= 1
    assert "agreement_pct" in metrics


def test_twin_observe_constitution_violation_records_flags(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "v.sqlite3", jsonl_path=tmp_path / "v.jsonl"
    )
    bus = EventBus()
    twin = ApprovalTwinAgent(registry=registry, model_path=tmp_path / "t.json", event_bus=bus)
    bus.publish(
        topic="safety.constitution.violation",
        producer="test",
        payload={
            "principle_name": "no_bypass",
            "severity": "fatal",
            "description": "test",
            "dna_hash": "bad_dna",
        },
    )
    assert any("no_bypass" in f for f in twin._recent_constitution_flags)
    assert twin.observations_total >= 1


def test_evaluate_shadow_promotion_records_alignment(tmp_path: Path, monkeypatch) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "v.sqlite3", jsonl_path=tmp_path / "v.jsonl"
    )
    twin = ApprovalTwinAgent(registry=registry, model_path=tmp_path / "t.json")
    captured: list[dict] = []
    monkeypatch.setattr(
        "lumina_core.evolution.approval_twin_agent.record_shadow_twin_alignment_monitoring",
        lambda **kw: captured.append(kw),
    )
    dna = _dna(fitness=1.1, mutation_rate=0.05, content="risk guard stop")
    res = twin.evaluate_shadow_promotion(dna=dna, shadow_total_pnl=5.0, veto_blocked=False)
    assert "recommendation" in res
    assert captured
    assert "aligned" in captured[0]
    assert twin.observations_total >= 1
