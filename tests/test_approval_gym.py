from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.approval_gym import ApprovalGym
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.steve_values_registry import SteveValuesRegistry


def _sample_dna(seed: str, fitness: float, generation: int) -> PolicyDNA:
    return PolicyDNA.create(
        prompt_id="approval_gym",
        version="candidate",
        content={"seed": seed},
        fitness_score=fitness,
        generation=generation,
        lineage_hash="GENESIS",
    )


def test_approval_gym_generates_between_3_and_5_proposals_with_history(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "values.sqlite3",
        jsonl_path=tmp_path / "values.jsonl",
    )
    gym = ApprovalGym(registry=registry, rng_seed=7)
    proposals = gym.generate_proposals(
        historical_dna=[_sample_dna("a", 0.8, 1), _sample_dna("b", 1.1, 2)],
    )

    assert 3 <= len(proposals) <= 5
    assert all(bool(item.dna_hash) for item in proposals)


def test_approval_gym_run_session_stores_answers(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "values.sqlite3",
        jsonl_path=tmp_path / "values.jsonl",
    )
    gym = ApprovalGym(registry=registry, rng_seed=11)
    answers = iter(["APPROVE", "VETO", "APPROVE"])

    records = gym.run_session(
        historical_dna=[_sample_dna("a", 0.3, 1)],
        count=3,
        ask_fn=lambda _vraag: next(answers),
    )

    assert len(records) == 3
    assert records[0].steve_antwoord == "APPROVE"
    assert records[1].steve_antwoord == "VETO"
    recent = registry.list_recent(limit=10)
    assert len(recent) == 3
