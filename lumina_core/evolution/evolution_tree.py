"""Headless DNA lineage graph builder for GET /api/evolution/tree (no Streamlit)."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA

_EVOLUTION_LOG = Path(os.getenv("EVOLUTION_LOG_PATH", "state/evolution_log.jsonl"))
_EVOLUTION_DECISIONS = Path(os.getenv("EVOLUTION_DECISIONS_PATH", "state/evolution_decisions.jsonl"))


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _mutation_depth(mutation_rate: float) -> str:
    if mutation_rate >= 0.35:
        return "radical"
    if mutation_rate >= 0.15:
        return "moderate"
    return "conservative"


def _infer_status(dna: PolicyDNA, *, active_hash: str | None, champion_hash: str | None, rejected: set[str]) -> str:
    if dna.hash in rejected:
        return "rejected"
    if active_hash and dna.hash == active_hash:
        return "active"
    if champion_hash and dna.hash == champion_hash:
        return "champion"
    version = str(dna.version).lower()
    if version in {"active", "champion"}:
        return "active" if version == "active" else "champion"
    if version in {"candidate", "proposed", "draft"}:
        return "proposed"
    if version in {"archived", "archive"}:
        return "archived"
    return "archived"


def _load_rejected_hashes() -> set[str]:
    rejected: set[str] = set()
    if not _EVOLUTION_DECISIONS.exists():
        return rejected
    for raw in _EVOLUTION_DECISIONS.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("decision") == "rejected":
            h = entry.get("hash")
            if h:
                rejected.add(str(h))
    return rejected


def _load_pending_mutations() -> list[dict[str, Any]]:
    if not _EVOLUTION_LOG.exists():
        return []
    decisions: set[str] = set()
    if _EVOLUTION_DECISIONS.exists():
        for raw in _EVOLUTION_DECISIONS.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            h = entry.get("hash")
            if h:
                decisions.add(str(h))
    pending: list[dict[str, Any]] = []
    for raw in _EVOLUTION_LOG.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("status") != "proposed":
            continue
        proposal_hash = str(entry.get("hash", ""))
        if not proposal_hash or proposal_hash in decisions:
            continue
        for challenger in entry.get("challengers", []):
            if not isinstance(challenger, dict):
                continue
            dna_hash = str(challenger.get("dna_hash") or challenger.get("hash") or proposal_hash)
            pending.append(
                {
                    "proposal_id": proposal_hash,
                    "dna_hash": dna_hash,
                    "status": "proposed",
                    "fitness_score": float(challenger.get("confidence", challenger.get("fitness_score", 0.55)) or 0.55),
                    "shadow_verdict": None,
                    "requires_human_approval": bool(entry.get("requires_human_approval", False)),
                }
            )
    return pending


def _dna_to_node(
    dna: PolicyDNA,
    *,
    active_hash: str | None,
    champion_hash: str | None,
    rejected: set[str],
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
        "status": _infer_status(
            dna,
            active_hash=active_hash,
            champion_hash=champion_hash,
            rejected=rejected,
        ),
        "mutation_depth": _mutation_depth(float(dna.mutation_rate)),
        "content_digest": _content_digest(dna.content),
    }


def _mutation_type(parent_count: int) -> str:
    if parent_count >= 2:
        return "crossover"
    if parent_count == 0:
        return "bootstrap"
    return "mutate"


def build_evolution_tree(
    *,
    depth: int = 10,
    include_rejected: bool = False,
    root_hash: str | None = None,
    registry: DNARegistry | None = None,
) -> dict[str, Any]:
    """Build DNA lineage graph payload aligned with EvolutionTreeResponse schema."""
    reg = registry or DNARegistry()
    max_depth = max(1, min(int(depth), 20))
    rejected = _load_rejected_hashes()

    active_dna = reg.get_latest_dna(version="active") or reg.get_latest_dna()
    ranked = reg.get_ranked_dna(limit=max(3, max_depth * 2))
    champion_dna = ranked[0] if ranked else active_dna
    active_hash = active_dna.hash if active_dna else None
    champion_hash = champion_dna.hash if champion_dna else active_hash

    all_dna = reg.list_all_dna(limit=max_depth * 50)
    if root_hash:
        by_hash = {d.hash: d for d in all_dna}
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
        status = _infer_status(
            dna,
            active_hash=active_hash,
            champion_hash=champion_hash,
            rejected=rejected,
        )
        if status == "rejected" and not include_rejected:
            continue
        nodes.append(
            _dna_to_node(
                dna,
                active_hash=active_hash,
                champion_hash=champion_hash,
                rejected=rejected,
            )
        )
        for parent_id in dna.parent_ids:
            edges.append(
                {
                    "from_hash": str(parent_id),
                    "to_hash": dna.hash,
                    "mutation_type": _mutation_type(len(dna.parent_ids)),
                }
            )

    champion_node = next((n for n in nodes if n["hash"] == champion_hash), None)
    if champion_node is None and champion_dna is not None:
        champion_node = _dna_to_node(
            champion_dna,
            active_hash=active_hash,
            champion_hash=champion_hash,
            rejected=rejected,
        )

    mode = str(os.getenv("LUMINA_MODE") or os.getenv("TRADE_MODE") or "sim").strip().lower() or "sim"

    return {
        "schema_version": "1.0",
        "ts": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "active_hash": active_hash or "",
        "champion": champion_node,
        "nodes": nodes,
        "edges": edges,
        "pending_mutations": _load_pending_mutations(),
    }
