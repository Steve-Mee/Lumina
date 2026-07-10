"""Partial DNA registration on birth stall."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.dna_handoff import register_partial_birth_dna, resolve_birth_gen0_dna
from lumina_core.evolution.dna_registry import DNARegistry


@pytest.mark.unit
def test_register_partial_birth_dna_seeds_gen0(tmp_path: Path) -> None:
    register_partial_birth_dna(
        tmp_path,
        curriculum_stage="stage1_trend",
        stage_trades=400,
        stage_winrate=0.36,
        oos_proxy_winrate=0.38,
        policy_path=str(tmp_path / "policy.zip"),
        stall_reason="plateau_evolution_exhausted",
    )
    registry = DNARegistry(
        jsonl_path=tmp_path / "state" / "dna_registry.jsonl",
        sqlite_path=tmp_path / "state" / "dna_registry.sqlite3",
    )
    dna = resolve_birth_gen0_dna(registry)
    assert dna is not None
    assert dna.prompt_id == "birth_v2_partial"
    content = dna.content if isinstance(dna.content, dict) else json.loads(dna.content)
    assert content.get("graduation_tier") == "provisional"
    assert float(dna.fitness_score) >= 0.38