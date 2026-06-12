"""Tests for headless evolution tree builder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA
from lumina_core.evolution.evolution_tree import build_evolution_tree


@pytest.mark.unit
def test_build_evolution_tree_empty_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sqlite = tmp_path / "dna.sqlite3"
    jsonl = tmp_path / "dna.jsonl"
    registry = DNARegistry(jsonl_path=jsonl, sqlite_path=sqlite)
    payload = build_evolution_tree(depth=5, registry=registry)
    assert payload["schema_version"] == "1.0"
    assert payload["nodes"] == []
    assert payload["edges"] == []
    assert payload["active_hash"] == ""
    assert payload["champion"] is None


@pytest.mark.unit
def test_build_evolution_tree_with_lineage(tmp_path: Path) -> None:
    sqlite = tmp_path / "dna.sqlite3"
    jsonl = tmp_path / "dna.jsonl"
    registry = DNARegistry(jsonl_path=jsonl, sqlite_path=sqlite)
    parent = PolicyDNA.create(
        prompt_id="genesis",
        version="active",
        content={"seed": True},
        fitness_score=0.7,
        generation=0,
    )
    registry.register_dna(parent)
    child = registry.mutate(parent=parent, mutation_rate=0.2, version="candidate", fitness_score=0.75)
    registry.register_dna(child)

    payload = build_evolution_tree(depth=10, registry=registry)
    assert len(payload["nodes"]) >= 2
    assert any(edge["to_hash"] == child.hash for edge in payload["edges"])
    assert payload["active_hash"] == parent.hash
