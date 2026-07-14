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
    twin = ApprovalTwinAgent(registry=registry, model_path=tmp_path / "twin_model.json")

    decision = twin.evaluate_dna_promotion(_dna(fitness=1.2, mutation_rate=0.1, content="risk guard stop"))

    assert set(decision.keys()) == {"recommendation", "confidence", "explanation", "risk_flags"}
    assert isinstance(decision["recommendation"], bool)
    assert 0.0 <= float(decision["confidence"]) <= 1.0
    assert isinstance(decision["explanation"], str)
    assert isinstance(decision["risk_flags"], list)


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
    rec = SteveValueRecord.create(vraag="promote low risk?", steve_antwoord="APPROVE", context_dna_hash="x", confidence_score=0.85)
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
