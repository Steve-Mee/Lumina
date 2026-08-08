"""DNARegistry implementation."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from lumina_core.state.state_manager import safe_append_jsonl, safe_sqlite_connect
from lumina_core.agent_orchestration.schemas import (
    BLACKBOARD_TOPIC_MODELS,
    EVENT_BUS_TOPIC_MODELS,
    TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
    typed_payload_from_event,
)
from lumina_core.evolution.policy_dna import PolicyDNA, _canonical_content

logger = logging.getLogger(__name__)

_SNAPSHOT_TOPIC_MODELS: dict[str, type[BaseModel]] = {
    **BLACKBOARD_TOPIC_MODELS,
    **EVENT_BUS_TOPIC_MODELS,
}

def _snapshot_payload_from_event(event: Any, *, topic: str) -> dict[str, Any]:
    """Validated snapshot dict for DNA bootstrap (typed when topic is registered)."""
    topic_key = str(topic).strip().lower()
    model = _SNAPSHOT_TOPIC_MODELS.get(topic_key)
    if model is not None:
        try:
            return typed_payload_from_event(event, model).model_dump(mode="json", exclude_none=False)
        except ValidationError:
            pass
    payload = getattr(event, "payload", None)
    if isinstance(payload, dict):
        return dict(payload)
    return {}


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
                        logging.exception(
                            "Unhandled broad exception fallback in lumina_core/evolution/dna_registry.py:199"
                        )
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

    def list_all_dna(self, *, limit: int = 500) -> list[PolicyDNA]:
        """Return DNA entries newest-first (for lineage graph endpoints)."""
        query = (
            "SELECT prompt_id, version, hash, content, fitness_score, generation, parent_ids, "
            "mutation_rate, lineage_hash, created_at "
            "FROM dna_entries ORDER BY datetime(created_at) DESC, rowid DESC LIMIT ?"
        )
        cap = max(1, int(limit))
        with self._lock:
            if not self.sqlite_path.exists():
                return []
            with safe_sqlite_connect(self.sqlite_path) as connection:
                rows = connection.execute(query, (cap,)).fetchall()
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

        # === Phase 2 Deliverable 5 (Aperture Hardening) — First structural hook ===
        # Any DNA created through the normal registry path that touches risk logic
        # (hyperparams, high mutation, martingale, etc.) now automatically receives
        # isolated shadow aperture treatment. This is the first central enforcement
        # point instead of scattered manual wiring in every caller.
        #
        # Best-effort and non-breaking by design (consistent with all prior D5 slices).
        try:
            from .risk_shadow_bridge import ensure_risk_shadow_for_dna_content
            from pathlib import Path

            ensure_risk_shadow_for_dna_content(
                next_content,
                engine=None,
                storage_path=Path("state/risk_shadow_evolution.jsonl"),
            )
        except Exception:
            # Structural protection must never break DNA creation or evolution.
            pass
        # ================================================================================

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
        event_bus: Any | None = None,
        prompt_id: str = "blackboard_snapshot",
        version: str = "blackboard_bootstrap",
        fitness_score: float = 0.0,
    ) -> PolicyDNA | None:
        bb_ok = blackboard is not None and hasattr(blackboard, "latest")
        eb_ok = event_bus is not None and hasattr(event_bus, "latest")
        if not bb_ok and not eb_ok:
            return None
        snapshot: dict[str, Any] = {}
        lineage_parts: list[str] = []
        exec_topic = TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
        for topic in ("meta.reflection", "meta.hyperparameters", "agent.meta.proposal", exec_topic):
            event = None
            try:
                if topic == exec_topic:
                    if eb_ok:
                        event = event_bus.latest(exec_topic)
                elif bb_ok:
                    event = blackboard.latest(topic)
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/evolution/dna_registry.py:319")
                event = None
            if event is None:
                continue
            snapshot[topic] = _snapshot_payload_from_event(event, topic=topic)
            ev_hash = getattr(event, "event_hash", None)
            if not ev_hash and hasattr(event, "to_dict"):
                ev_hash = hashlib.sha256(
                    json.dumps(event.to_dict(), sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
            lineage_parts.append(str(ev_hash or "GENESIS"))
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
