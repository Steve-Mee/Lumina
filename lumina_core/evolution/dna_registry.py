from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.state.state_manager import safe_append_jsonl, safe_sqlite_connect


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


class DNARegistry:
    _instances: dict[tuple[str, str], "DNARegistry"] = {}
    _instances_lock = threading.RLock()

    def __new__(
        cls,
        *,
        jsonl_path: Path | str = Path("state/dna_registry.jsonl"),
        sqlite_path: Path | str = Path("state/dna_registry.sqlite3"),
    ) -> "DNARegistry":
        key = (str(Path(jsonl_path)), str(Path(sqlite_path)))
        with cls._instances_lock:
            instance = cls._instances.get(key)
            if instance is None:
                instance = super().__new__(cls)
                cls._instances[key] = instance
        return instance

    def __init__(
        self,
        *,
        jsonl_path: Path | str = Path("state/dna_registry.jsonl"),
        sqlite_path: Path | str = Path("state/dna_registry.sqlite3"),
    ) -> None:
        if getattr(self, "_initialized", False):
            return
        self.jsonl_path = Path(jsonl_path)
        self.sqlite_path = Path(sqlite_path)
        self._lock = threading.RLock()
        self._initialized = True
        self._ensure_storage()

    def register_dna(self, dna: PolicyDNA) -> PolicyDNA:
        record = dna.to_record()
        with self._lock:
            self._ensure_storage()
            with safe_sqlite_connect(self.sqlite_path) as connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO dna_entries (
                        hash,
                        prompt_id,
                        version,
                        content,
                        fitness_score,
                        generation,
                        parent_ids,
                        mutation_rate,
                        lineage_hash,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record["hash"],
                        record["prompt_id"],
                        record["version"],
                        record["content"],
                        record["fitness_score"],
                        record["generation"],
                        json.dumps(record["parent_ids"], ensure_ascii=True),
                        record["mutation_rate"],
                        record["lineage_hash"],
                        record["created_at"],
                    ),
                )
                inserted = connection.total_changes > 0
                if inserted:
                    try:
                        self._append_jsonl(record)
                    except Exception:
                        connection.execute("DELETE FROM dna_entries WHERE hash = ?", (record["hash"],))
                        connection.commit()
                        raise
                connection.commit()
        return dna

    def get_latest_dna(self, version: str | None = None) -> PolicyDNA | None:
        query = (
            "SELECT prompt_id, version, hash, content, fitness_score, generation, parent_ids, mutation_rate, lineage_hash, created_at "
            "FROM dna_entries"
        )
        params: tuple[Any, ...] = ()
        if version is not None:
            query += " WHERE version = ?"
            params = (str(version),)
        query += " ORDER BY datetime(created_at) DESC, rowid DESC LIMIT 1"

        with self._lock:
            if not self.sqlite_path.exists():
                return None
            with safe_sqlite_connect(self.sqlite_path) as connection:
                row = connection.execute(query, params).fetchone()
        if row is None:
            return None
        return PolicyDNA.from_record(
            {
                "prompt_id": row[0],
                "version": row[1],
                "hash": row[2],
                "content": row[3],
                "fitness_score": row[4],
                "generation": row[5],
                "parent_ids": json.loads(row[6]) if row[6] else [],
                "mutation_rate": row[7],
                "lineage_hash": row[8],
                "created_at": row[9],
            }
        )

    def get_ranked_dna(self, *, limit: int = 3, versions: tuple[str, ...] | None = None) -> list[PolicyDNA]:
        query = (
            "SELECT prompt_id, version, hash, content, fitness_score, generation, parent_ids, mutation_rate, lineage_hash, created_at "
            "FROM dna_entries"
        )
        params: list[Any] = []
        if versions:
            placeholders = ", ".join("?" for _ in versions)
            query += f" WHERE version IN ({placeholders})"
            params.extend(str(version) for version in versions)
        query += " ORDER BY fitness_score DESC, generation DESC, datetime(created_at) DESC LIMIT ?"
        params.append(max(1, int(limit)))

        with self._lock:
            if not self.sqlite_path.exists():
                return []
            with safe_sqlite_connect(self.sqlite_path) as connection:
                rows = connection.execute(query, tuple(params)).fetchall()
        return [
            PolicyDNA.from_record(
                {
                    "prompt_id": row[0],
                    "version": row[1],
                    "hash": row[2],
                    "content": row[3],
                    "fitness_score": row[4],
                    "generation": row[5],
                    "parent_ids": json.loads(row[6]) if row[6] else [],
                    "mutation_rate": row[7],
                    "lineage_hash": row[8],
                    "created_at": row[9],
                }
            )
            for row in rows
        ]

    def mutate(
        self,
        *,
        parent: PolicyDNA,
        mutation_rate: float,
        content: Any | None = None,
        fitness_score: float | None = None,
        version: str | None = None,
        lineage_hash: str | None = None,
        crossover: PolicyDNA | None = None,
    ) -> PolicyDNA:
        next_content = _canonical_content(content if content is not None else parent.content)
        next_generation = int(parent.generation) + 1
        parent_ids = [parent.hash]
        if crossover is not None:
            parent_ids.append(crossover.hash)
            if content is None:
                next_content = self._blend_content(parent.content, crossover.content)
        return PolicyDNA.create(
            prompt_id=parent.prompt_id,
            version=str(version or parent.version),
            content=next_content,
            fitness_score=float(parent.fitness_score if fitness_score is None else fitness_score),
            generation=next_generation,
            parent_ids=parent_ids,
            mutation_rate=float(mutation_rate),
            lineage_hash=str(lineage_hash or parent.lineage_hash),
        )

    def load_from_blackboard(
        self,
        blackboard: Any,
        *,
        prompt_id: str = "blackboard_snapshot",
        version: str = "blackboard_bootstrap",
        fitness_score: float = 0.0,
    ) -> PolicyDNA | None:
        if blackboard is None or not hasattr(blackboard, "latest"):
            return None
        snapshot: dict[str, Any] = {}
        lineage_parts: list[str] = []
        for topic in ("meta.reflection", "meta.hyperparameters", "agent.meta.proposal", "execution.aggregate"):
            try:
                event = blackboard.latest(topic)
            except Exception:
                event = None
            if event is None:
                continue
            payload = getattr(event, "payload", {}) if isinstance(getattr(event, "payload", {}), dict) else {}
            snapshot[topic] = payload
            lineage_parts.append(str(getattr(event, "event_hash", "GENESIS") or "GENESIS"))
        if not snapshot:
            return None
        lineage_hash = (
            hashlib.sha256("|".join(lineage_parts).encode("utf-8")).hexdigest() if lineage_parts else "GENESIS"
        )
        dna = PolicyDNA.create(
            prompt_id=prompt_id,
            version=version,
            content=snapshot,
            fitness_score=float(fitness_score),
            generation=0,
            mutation_rate=0.0,
            lineage_hash=lineage_hash,
        )
        return self.register_dna(dna)

    def _ensure_storage(self) -> None:
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        with safe_sqlite_connect(self.sqlite_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dna_entries (
                    hash TEXT PRIMARY KEY,
                    prompt_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    content TEXT NOT NULL,
                    fitness_score REAL NOT NULL,
                    generation INTEGER NOT NULL,
                    parent_ids TEXT NOT NULL,
                    mutation_rate REAL NOT NULL,
                    lineage_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_dna_entries_version_created_at ON dna_entries(version, created_at DESC)"
            )
            connection.commit()
        if not self.jsonl_path.exists():
            self.jsonl_path.touch()

    def _append_jsonl(self, record: dict[str, Any]) -> None:
        safe_append_jsonl(self.jsonl_path, record, hash_chain=False)

    @staticmethod
    def _blend_content(left: str, right: str) -> str:
        if not left:
            return right
        if not right:
            return left
        midpoint_left = max(1, len(left) // 2)
        midpoint_right = max(1, len(right) // 2)
        return left[:midpoint_left].rstrip() + "\n" + right[midpoint_right:].lstrip()
