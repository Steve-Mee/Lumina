from __future__ import annotations

import json
from pathlib import Path

from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA


def test_dna_registry_registers_and_reads_latest(tmp_path: Path) -> None:
    registry = DNARegistry(
        jsonl_path=tmp_path / "dna_registry.jsonl",
        sqlite_path=tmp_path / "dna_registry.sqlite3",
    )

    dna = PolicyDNA.create(
        prompt_id="policy",
        version="active",
        content={"prompt": "hold when unclear"},
        fitness_score=1.25,
        generation=0,
        lineage_hash="abc123",
    )
    registry.register_dna(dna)

    latest = registry.get_latest_dna("active")

    assert latest is not None
    assert latest.hash == dna.hash
    assert latest.lineage_hash == "abc123"
    assert (tmp_path / "dna_registry.jsonl").exists()
    assert (tmp_path / "dna_registry.sqlite3").exists()


def test_dna_registry_mutate_and_load_from_blackboard(tmp_path: Path) -> None:
    registry = DNARegistry(
        jsonl_path=tmp_path / "dna_registry.jsonl",
        sqlite_path=tmp_path / "dna_registry.sqlite3",
    )
    blackboard = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    blackboard.publish_sync(
        topic="meta.reflection",
        producer="meta_agent_orchestrator",
        payload={"sharpe": 1.1, "win_rate": 0.56},
        confidence=0.9,
    )

    bootstrap = registry.load_from_blackboard(blackboard)
    assert bootstrap is not None

    mutated = registry.mutate(
        parent=bootstrap,
        mutation_rate=0.2,
        content={"prompt": "favor hold under drift"},
        fitness_score=1.4,
        version="candidate",
    )
    registry.register_dna(mutated)

    latest = registry.get_latest_dna("candidate")
    assert latest is not None
    assert latest.parent_ids == (bootstrap.hash,)
    lines = (tmp_path / "dna_registry.jsonl").read_text(encoding="utf-8").strip().splitlines()
    payloads = [json.loads(line) for line in lines]
    assert len(payloads) == 2