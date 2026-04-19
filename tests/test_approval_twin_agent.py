from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.approval_twin_agent import ApprovalTwinAgent
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.steve_values_registry import SteveValueRecord, SteveValuesRegistry


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
