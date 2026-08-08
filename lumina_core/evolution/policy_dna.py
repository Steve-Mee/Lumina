"""PolicyDNA model and hash helpers."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freeze_parent_ids(parent_ids: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not parent_ids:
        return ()
    return tuple(str(parent_id) for parent_id in parent_ids)


def _canonical_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    return json.dumps(content, sort_keys=True, ensure_ascii=True)


def _compute_hash(
    *,
    prompt_id: str,
    version: str,
    content: str,
    fitness_score: float,
    generation: int,
    parent_ids: tuple[str, ...],
    mutation_rate: float,
    lineage_hash: str,
) -> str:
    canonical = json.dumps(
        {
            "prompt_id": prompt_id,
            "version": version,
            "content": content,
            "fitness_score": round(float(fitness_score), 8),
            "generation": int(generation),
            "parent_ids": list(parent_ids),
            "mutation_rate": round(float(mutation_rate), 8),
            "lineage_hash": lineage_hash,
        },
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class PolicyDNA:
    prompt_id: str
    version: str
    hash: str
    content: str
    fitness_score: float
    generation: int
    parent_ids: tuple[str, ...] = field(default_factory=tuple)
    mutation_rate: float = 0.0
    lineage_hash: str = "GENESIS"
    created_at: str = field(default_factory=_utcnow)

    @classmethod
    def create(
        cls,
        *,
        prompt_id: str,
        version: str,
        content: Any,
        fitness_score: float,
        generation: int,
        parent_ids: list[str] | tuple[str, ...] | None = None,
        mutation_rate: float = 0.0,
        lineage_hash: str = "GENESIS",
        created_at: str | None = None,
    ) -> "PolicyDNA":
        canonical_content = _canonical_content(content)
        frozen_parent_ids = _freeze_parent_ids(parent_ids)

        # === Phase 2 Deliverable 5 — Belt-and-suspenders structural hook ===
        # Even direct PolicyDNA.create calls (bypassing mutate) now get protected.
        try:
            from .risk_shadow_bridge import ensure_risk_shadow_for_dna_content
            from pathlib import Path
            ensure_risk_shadow_for_dna_content(
                canonical_content,
                engine=None,
                storage_path=Path("state/risk_shadow_evolution.jsonl"),
            )
        except Exception:
            pass
        # ================================================================================

        return cls(
            prompt_id=str(prompt_id),
            version=str(version),
            hash=_compute_hash(
                prompt_id=str(prompt_id),
                version=str(version),
                content=canonical_content,
                fitness_score=float(fitness_score),
                generation=int(generation),
                parent_ids=frozen_parent_ids,
                mutation_rate=float(mutation_rate),
                lineage_hash=str(lineage_hash or "GENESIS"),
            ),
            content=canonical_content,
            fitness_score=float(fitness_score),
            generation=int(generation),
            parent_ids=frozen_parent_ids,
            mutation_rate=float(mutation_rate),
            lineage_hash=str(lineage_hash or "GENESIS"),
            created_at=str(created_at or _utcnow()),
        )

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "PolicyDNA":
        return cls(
            prompt_id=str(record["prompt_id"]),
            version=str(record["version"]),
            hash=str(record["hash"]),
            content=str(record["content"]),
            fitness_score=float(record.get("fitness_score", 0.0) or 0.0),
            generation=int(record.get("generation", 0) or 0),
            parent_ids=_freeze_parent_ids(record.get("parent_ids")),
            mutation_rate=float(record.get("mutation_rate", 0.0) or 0.0),
            lineage_hash=str(record.get("lineage_hash", "GENESIS") or "GENESIS"),
            created_at=str(record.get("created_at", _utcnow())),
        )

    def to_record(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parent_ids"] = list(self.parent_ids)
        return payload
