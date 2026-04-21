from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BibleEntry:
    timestamp: str
    entry_type: str
    dna_hash: str
    lineage_hash: str
    generation: int
    fitness: float
    hypothesis: str
    code: str
    status: str
    previous_hash: str
    entry_hash: str


class LuminaBible:
    """Append-only knowledge base for generated strategy rules."""

    def __init__(self, *, path: Path | str = Path("state/lumina_bible_generated_strategies.jsonl")) -> None:
        self.path = Path(path)
        self._lock = RLock()

    def append_generated_rule(
        self,
        *,
        dna_hash: str,
        lineage_hash: str,
        generation: int,
        fitness: float,
        hypothesis: str,
        code: str,
        status: str = "winner",
    ) -> BibleEntry:
        with self._lock:
            previous_hash = self._get_last_entry_hash()
            record = {
                "timestamp": _utcnow(),
                "entry_type": "generated_strategy_rule",
                "dna_hash": str(dna_hash),
                "lineage_hash": str(lineage_hash),
                "generation": int(generation),
                "fitness": float(fitness),
                "hypothesis": str(hypothesis),
                "code": str(code),
                "status": str(status),
                "previous_hash": str(previous_hash),
            }
            canonical = json.dumps(record, sort_keys=True, ensure_ascii=True)
            record["entry_hash"] = _sha256(canonical)

            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        return BibleEntry(**record)

    def list_recent_generated_rules(self, *, limit: int = 25) -> list[dict[str, Any]]:
        with self._lock:
            if not self.path.exists():
                return []
            rows: list[dict[str, Any]] = []
            with self.path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        payload = json.loads(raw)
                    except Exception:
                        continue
                    if isinstance(payload, dict) and payload.get("entry_type") == "generated_strategy_rule":
                        rows.append(payload)
            return rows[-max(1, int(limit)) :]

    def _get_last_entry_hash(self) -> str:
        if not self.path.exists():
            return "GENESIS"
        last_hash = "GENESIS"
        with self.path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    last_hash = str(payload.get("entry_hash", last_hash) or last_hash)
        return last_hash
