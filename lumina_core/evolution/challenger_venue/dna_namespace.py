"""Challenger DNA registry namespace — never champion active (K2)."""

from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA

CHALLENGER_VERSION = "challenger"


def challenger_state_root(workspace: Path | str) -> Path:
    return Path(workspace) / "state" / "challenger_venue"


def challenger_registry(workspace: Path | str) -> DNARegistry:
    root = challenger_state_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    return DNARegistry(
        jsonl_path=root / "dna.jsonl",
        sqlite_path=root / "dna.sqlite3",
    )


def register_challenger_dna(workspace: Path | str, dna: PolicyDNA) -> PolicyDNA:
    """Register into challenger namespace. Version is forced off 'active'."""
    version = str(dna.version or CHALLENGER_VERSION)
    if version.strip().lower() == "active":
        version = CHALLENGER_VERSION
    stamped = PolicyDNA.create(
        prompt_id=dna.prompt_id,
        version=version,
        content=dna.content,
        fitness_score=dna.fitness_score,
        generation=dna.generation,
        parent_ids=list(dna.parent_ids),
        mutation_rate=dna.mutation_rate,
        lineage_hash=dna.lineage_hash,
        created_at=dna.created_at,
    )
    return challenger_registry(workspace).register_dna(stamped)
