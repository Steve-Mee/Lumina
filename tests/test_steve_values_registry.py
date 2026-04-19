from __future__ import annotations

import json
from pathlib import Path

from lumina_core.evolution.steve_values_registry import SteveValueRecord, SteveValuesRegistry


def test_steve_values_registry_append_and_list_recent(tmp_path: Path) -> None:
    registry = SteveValuesRegistry(
        sqlite_path=tmp_path / "steve_values.sqlite3",
        jsonl_path=tmp_path / "steve_values.jsonl",
    )

    first = SteveValueRecord.create(
        vraag="Zou je hash aaa naar REAL zetten?",
        steve_antwoord="VETO",
        context_dna_hash="aaa",
        confidence_score=0.2,
    )
    second = SteveValueRecord.create(
        vraag="Zou je hash bbb naar REAL zetten?",
        steve_antwoord="APPROVE",
        context_dna_hash="bbb",
        confidence_score=0.9,
    )

    registry.append(first)
    registry.append(second)

    latest = registry.list_recent(limit=2)
    assert len(latest) == 2
    assert latest[0].context_dna_hash == "bbb"
    assert latest[1].context_dna_hash == "aaa"

    lines = (tmp_path / "steve_values.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    payloads = [json.loads(line) for line in lines]
    assert payloads[0]["context_dna_hash"] == "aaa"
    assert payloads[1]["context_dna_hash"] == "bbb"
