"""Veto registry: immutable append-only storage for human veto decisions on DNA promotions."""

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path


@dataclass(frozen=True)
class VetoRecord:
    """Immutable veto decision record."""
    veto_timestamp: str  # ISO format timestamp when veto was issued
    dna_id: str  # Identifier of DNA being vetoed
    dna_fitness: float  # Fitness of vetoed DNA
    reason: str  # Human-readable reason for veto
    issuer: str  # Who issued the veto (e.g., "Steve", "approval_twin_gate")
    metadata: dict  # Optional metadata (proposal details, conditions, etc.)


class VetoRegistry:
    """Append-only veto registry with dual SQLite+JSONL persistence.
    
    All write operations are fail-closed: if veto record creation fails,
    the registry state is unchanged. Query operations are read-only and
    cannot affect registry state.
    """

    def __init__(self, db_path: str = "state/veto_registry.db", log_path: str = "state/veto_registry.jsonl"):
        """Initialize veto registry.
        
        Args:
            db_path: Path to SQLite database file
            log_path: Path to JSONL audit log file
        """
        self._db_path = Path(db_path)
        self._log_path = Path(log_path)
        self._lock = threading.RLock()

        # Ensure directories exist
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        with self._lock:
            self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite schema if not present."""
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS veto_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                veto_timestamp TEXT NOT NULL,
                dna_id TEXT NOT NULL,
                dna_fitness REAL NOT NULL,
                reason TEXT NOT NULL,
                issuer TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def append_veto(self, record: VetoRecord) -> None:
        """Append veto record (thread-safe, fail-closed).
        
        Args:
            record: VetoRecord to append
            
        Raises:
            RuntimeError: If append operation fails (veto NOT recorded)
        """
        with self._lock:
            try:
                # Write to SQLite
                conn = sqlite3.connect(str(self._db_path))
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    INSERT INTO veto_records (veto_timestamp, dna_id, dna_fitness, reason, issuer, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    record.veto_timestamp,
                    record.dna_id,
                    record.dna_fitness,
                    record.reason,
                    record.issuer,
                    json.dumps(record.metadata),
                ))
                conn.commit()
                conn.close()

                # Write to JSONL (append-only audit log)
                with open(self._log_path, "a") as f:
                    f.write(json.dumps(asdict(record)) + "\n")

            except Exception as e:
                raise RuntimeError(f"Failed to append veto record: {e}")

    def is_veto_active(self, dna_id: str, window_seconds: int = 1800) -> bool:
        """Check if DNA has active veto within window (fail-closed: True blocks promotion).
        
        Args:
            dna_id: DNA identifier to check
            window_seconds: Veto window duration in seconds (default 30 min = 1800 sec)
            
        Returns:
            True if veto found within window (blocks promotion), False otherwise
        """
        with self._lock:
            try:
                # Calculate cutoff timestamp
                cutoff_time = datetime.utcnow() - timedelta(seconds=window_seconds)
                cutoff_iso = cutoff_time.isoformat()

                conn = sqlite3.connect(str(self._db_path))
                cursor = conn.execute("""
                    SELECT id FROM veto_records
                    WHERE dna_id = ? AND veto_timestamp >= ?
                    LIMIT 1
                """, (dna_id, cutoff_iso))
                result = cursor.fetchone()
                conn.close()

                return result is not None
            except Exception:
                # Fail-closed: if query fails, assume veto is active
                return True

    def list_recent(self, limit: int = 10, dna_id_filter: str | None = None) -> list[VetoRecord]:
        """List recent veto records (read-only query).
        
        Args:
            limit: Maximum number of records to return
            dna_id_filter: Optional DNA ID to filter by
            
        Returns:
            List of VetoRecord objects in reverse chronological order
        """
        with self._lock:
            try:
                conn = sqlite3.connect(str(self._db_path))
                if dna_id_filter:
                    cursor = conn.execute("""
                        SELECT veto_timestamp, dna_id, dna_fitness, reason, issuer, metadata
                        FROM veto_records
                        WHERE dna_id = ?
                        ORDER BY veto_timestamp DESC
                        LIMIT ?
                    """, (dna_id_filter, limit))
                else:
                    cursor = conn.execute("""
                        SELECT veto_timestamp, dna_id, dna_fitness, reason, issuer, metadata
                        FROM veto_records
                        ORDER BY veto_timestamp DESC
                        LIMIT ?
                    """, (limit,))

                records = []
                for row in cursor.fetchall():
                    veto_timestamp, dna_id, dna_fitness, reason, issuer, metadata_str = row
                    records.append(VetoRecord(
                        veto_timestamp=veto_timestamp,
                        dna_id=dna_id,
                        dna_fitness=dna_fitness,
                        reason=reason,
                        issuer=issuer,
                        metadata=json.loads(metadata_str),
                    ))
                conn.close()
                return records
            except Exception:
                return []
