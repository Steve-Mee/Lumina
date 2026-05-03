from __future__ import annotations
import logging

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from lumina_core.state.state_manager import safe_with_file_lock


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
            self._append_record(record)

        return BibleEntry(**record)

    def append_community_external_rule(
        self,
        *,
        source: str,
        hypothesis: str,
        excerpt: str,
        vetting: str = "shadow_twin_ok",
        fitness: float = 0.0,
        generation: int = 0,
        lineage_hash: str = "COMMUNITY",
    ) -> BibleEntry:
        """Append vetted external / community knowledge (post shadow + twin)."""
        with self._lock:
            previous_hash = self._get_last_entry_hash()
            record = {
                "timestamp": _utcnow(),
                "entry_type": "community_external_rule",
                "source": str(source),
                "hypothesis": str(hypothesis),
                "code": str(excerpt),
                "status": str(vetting),
                "generation": int(generation),
                "lineage_hash": str(lineage_hash),
                "fitness": float(fitness),
                "dna_hash": "community_external",
                "previous_hash": str(previous_hash),
            }
            canonical = json.dumps(record, sort_keys=True, ensure_ascii=True)
            record["entry_hash"] = _sha256(canonical)
            self._append_record(record)

        return BibleEntry(
            timestamp=record["timestamp"],
            entry_type=record["entry_type"],
            dna_hash=str(record["dna_hash"]),
            lineage_hash=record["lineage_hash"],
            generation=record["generation"],
            fitness=record["fitness"],
            hypothesis=record["hypothesis"],
            code=record["code"],
            status=record["status"],
            previous_hash=record["previous_hash"],
            entry_hash=record["entry_hash"],
        )

    def _dream_hint_fingerprint_recent(self, fingerprint: str) -> bool:
        if not self.path.exists() or not str(fingerprint).strip():
            return False
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        for raw in lines[-500:]:
            raw = raw.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/evolution/lumina_bible.py:133")
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("entry_type", "")) != "dream_rule_hint":
                continue
            if str(payload.get("fingerprint", "")) == str(fingerprint):
                return True
        return False

    def append_dream_rule_hint(
        self,
        *,
        hint: str,
        generation: int,
        breach_rate: float = 0.0,
    ) -> BibleEntry | None:
        """Record a compact proactive rule suggestion from the dream-engine what-if pass.

        Returns None when the same hint was already recorded recently (deduped), so logs stay valuable.
        """
        hyp = str(hint).strip()[:2000]
        if len(hyp) < 4:
            raise ValueError("dream rule hint is too short")
        fingerprint = _sha256(hyp)[:32]
        detail = f"Dream what-if tail: {hyp}. context breach_rate={float(breach_rate):.4f} gen={int(generation)}"
        with self._lock:
            if self._dream_hint_fingerprint_recent(fingerprint):
                return None
            previous_hash = self._get_last_entry_hash()
            record = {
                "timestamp": _utcnow(),
                "entry_type": "dream_rule_hint",
                "source": "dream_engine",
                "hypothesis": hyp,
                "code": detail,
                "status": "proactive_tail",
                "generation": int(generation),
                "lineage_hash": "DREAM",
                "fitness": 0.0,
                "dna_hash": "dream_engine",
                "fingerprint": fingerprint,
                "previous_hash": str(previous_hash),
            }
            canonical = json.dumps(record, sort_keys=True, ensure_ascii=True)
            record["entry_hash"] = _sha256(canonical)
            self._append_record(record)
        return BibleEntry(
            timestamp=record["timestamp"],
            entry_type=record["entry_type"],
            dna_hash=str(record["dna_hash"]),
            lineage_hash=record["lineage_hash"],
            generation=record["generation"],
            fitness=record["fitness"],
            hypothesis=record["hypothesis"],
            code=record["code"],
            status=record["status"],
            previous_hash=record["previous_hash"],
            entry_hash=record["entry_hash"],
        )

    def _append_record(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        def _write_locked(target: Path) -> None:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())

        safe_with_file_lock(self.path, _write_locked)

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
                        logging.exception(
                            "Unhandled broad exception fallback in lumina_core/evolution/lumina_bible.py:219"
                        )
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
                    logging.exception("Unhandled broad exception fallback in lumina_core/evolution/lumina_bible.py:236")
                    continue
                if isinstance(payload, dict):
                    last_hash = str(payload.get("entry_hash", last_hash) or last_hash)
        return last_hash
