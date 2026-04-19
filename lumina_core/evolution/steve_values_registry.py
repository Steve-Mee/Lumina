from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class SteveValueRecord:
    vraag: str
    steve_antwoord: str
    timestamp: str
    context_dna_hash: str
    confidence_score: float

    @classmethod
    def create(
        cls,
        *,
        vraag: str,
        steve_antwoord: str,
        context_dna_hash: str,
        confidence_score: float,
        timestamp: str | None = None,
    ) -> "SteveValueRecord":
        return cls(
            vraag=str(vraag).strip(),
            steve_antwoord=str(steve_antwoord).strip(),
            timestamp=str(timestamp or _utcnow()),
            context_dna_hash=str(context_dna_hash).strip(),
            confidence_score=max(0.0, min(1.0, float(confidence_score))),
        )


class SteveValuesRegistry:
    """Append-only registry for Steve's value judgments (SQLite + JSONL)."""

    def __init__(
        self,
        *,
        sqlite_path: Path | str = Path("state/steve_values_registry.sqlite3"),
        jsonl_path: Path | str = Path("state/steve_values_registry.jsonl"),
    ) -> None:
        self.sqlite_path = Path(sqlite_path)
        self.jsonl_path = Path(jsonl_path)
        self._lock = threading.RLock()
        self._ensure_storage()

    def append(self, record: SteveValueRecord) -> SteveValueRecord:
        payload = asdict(record)
        payload_json = json.dumps(payload, ensure_ascii=False)

        with self._lock:
            self._ensure_storage()
            with sqlite3.connect(self.sqlite_path) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                try:
                    connection.execute("BEGIN IMMEDIATE")
                    connection.execute(
                        """
                        INSERT INTO steve_values (
                            vraag,
                            steve_antwoord,
                            timestamp,
                            context_dna_hash,
                            confidence_score
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            payload["vraag"],
                            payload["steve_antwoord"],
                            payload["timestamp"],
                            payload["context_dna_hash"],
                            payload["confidence_score"],
                        ),
                    )
                    self._append_jsonl(payload_json)
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise
        return record

    def list_recent(self, *, limit: int = 100) -> list[SteveValueRecord]:
        query = (
            "SELECT vraag, steve_antwoord, timestamp, context_dna_hash, confidence_score "
            "FROM steve_values ORDER BY id DESC LIMIT ?"
        )
        with self._lock:
            if not self.sqlite_path.exists():
                return []
            with sqlite3.connect(self.sqlite_path) as connection:
                rows = connection.execute(query, (max(1, int(limit)),)).fetchall()
        return [
            SteveValueRecord(
                vraag=str(row[0]),
                steve_antwoord=str(row[1]),
                timestamp=str(row[2]),
                context_dna_hash=str(row[3]),
                confidence_score=float(row[4]),
            )
            for row in rows
        ]

    def _ensure_storage(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.sqlite_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS steve_values (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vraag TEXT NOT NULL,
                    steve_antwoord TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    context_dna_hash TEXT NOT NULL,
                    confidence_score REAL NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS steve_values_no_update
                BEFORE UPDATE ON steve_values
                BEGIN
                    SELECT RAISE(ABORT, 'steve_values is append-only');
                END;
                """
            )
            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS steve_values_no_delete
                BEFORE DELETE ON steve_values
                BEGIN
                    SELECT RAISE(ABORT, 'steve_values is append-only');
                END;
                """
            )
            connection.commit()

        if not self.jsonl_path.exists():
            self.jsonl_path.touch()

    def _append_jsonl(self, payload_json: str) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as handle:
            handle.write(payload_json + "\n")
            handle.flush()
            os.fsync(handle.fileno())
