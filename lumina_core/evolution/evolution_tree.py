"""DNA lineage graph for GET /api/evolution/tree (KEEP registry only)."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA


def _content_digest(content: str) -> str:
    return hashlib.sha256(str(content).encode("utf-8")).hexdigest()


def _mutation_depth(mutation_rate: float) -> str:
    if mutation_rate >= 0.35:
        return "radical"
    if mutation_rate >= 0.15:
        return "moderate"
    return "conservative"


def _infer_status(
    dna: PolicyDNA,
    *,
    active_hash: str | None,
    champion_hash: str | None,
) -> str:
    if active_hash and dna.hash == active_hash:
        return "active"
    if champion_hash and dna.hash == champion_hash:
        return "champion"
    version = str(dna.version).lower()
    if version in {"active", "champion", "candidate", "proposed", "draft", "archived", "archive"}:
        return "active" if version == "active" else ("champion" if version == "champion" else version)
    return "archived"


def _mutation_type(parent_count: int) -> str:
    if parent_count >= 2:
        return "crossover"
    if parent_count == 0:
        return "bootstrap"
    return "mutate"


def _dna_to_node(
    dna: PolicyDNA,
    *,
    active_hash: str | None,
    champion_hash: str | None,
) -> dict[str, Any]:
    return {
        "hash": dna.hash,
        "prompt_id": dna.prompt_id,
        "version": dna.version,
        "fitness_score": float(dna.fitness_score),
        "generation": int(dna.generation),
        "parent_ids": list(dna.parent_ids),
        "mutation_rate": float(dna.mutation_rate),
        "lineage_hash": dna.lineage_hash,
        "created_at": dna.created_at,
        "status": _infer_status(dna, active_hash=active_hash, champion_hash=champion_hash),
        "mutation_depth": _mutation_depth(float(dna.mutation_rate)),
        "content_digest": _content_digest(dna.content),
    }


def build_evolution_tree(
    *,
    depth: int = 10,
    include_rejected: bool = False,
    root_hash: str | None = None,
    registry: DNARegistry | None = None,
) -> dict[str, Any]:
    """Build DNA lineage from the KEEP registry. Birth-v1 pending mutations stay empty."""
    del include_rejected
    reg = registry or DNARegistry()
    max_depth = max(1, min(int(depth), 20))
    active_dna = reg.get_latest_dna(version="active") or reg.get_latest_dna()
    ranked = reg.get_ranked_dna(limit=max(3, max_depth * 2))
    champion_dna = ranked[0] if ranked else active_dna
    active_hash = active_dna.hash if active_dna else None
    champion_hash = champion_dna.hash if champion_dna else active_hash
    all_dna = reg.list_all_dna(limit=max_depth * 50)
    if root_hash:
        by_hash = {item.hash: item for item in all_dna}
        root = by_hash.get(root_hash)
        if root is not None:
            selected: dict[str, PolicyDNA] = {root.hash: root}
            frontier = [root]
            for _ in range(max_depth):
                next_frontier: list[PolicyDNA] = []
                for node in frontier:
                    for parent_id in node.parent_ids:
                        parent = by_hash.get(parent_id)
                        if parent is not None and parent.hash not in selected:
                            selected[parent.hash] = parent
                            next_frontier.append(parent)
                if not next_frontier:
                    break
                frontier = next_frontier
            all_dna = list(selected.values())

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for dna in all_dna:
        nodes.append(_dna_to_node(dna, active_hash=active_hash, champion_hash=champion_hash))
        for parent_id in dna.parent_ids:
            edges.append(
                {
                    "from_hash": str(parent_id),
                    "to_hash": dna.hash,
                    "mutation_type": _mutation_type(len(dna.parent_ids)),
                }
            )

    champion_node = next((item for item in nodes if item["hash"] == champion_hash), None)
    if champion_node is None and champion_dna is not None:
        champion_node = _dna_to_node(champion_dna, active_hash=active_hash, champion_hash=champion_hash)

    mode = str(os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE") or "sim").strip().lower() or "sim"
    return {
        "schema_version": "1.0",
        "ts": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "active_hash": active_hash or "",
        "champion": champion_node,
        "nodes": nodes,
        "edges": edges,
        "pending_mutations": [],
        "validation_gate": "RESEARCH_CHARTER",
        "archived_birth_v1": True,
    }
