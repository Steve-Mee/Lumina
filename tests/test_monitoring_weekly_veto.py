from __future__ import annotations

import importlib.util
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.mark.unit
def test_weekly_veto_summary_sqlite_counts_recent_rows_only(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    db_path = state / "veto_registry.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE veto_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                veto_timestamp TEXT NOT NULL,
                dna_id TEXT NOT NULL,
                dna_fitness REAL NOT NULL,
                reason TEXT NOT NULL,
                issuer TEXT NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        ts_recent = datetime.now(timezone.utc).isoformat()
        ts_old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        conn.execute(
            "INSERT INTO veto_records (veto_timestamp, dna_id, dna_fitness, reason, issuer, metadata) VALUES (?,?,?,?,?,?)",
            (ts_recent, "dna1", 1.0, "too_risky", "twin", "{}"),
        )
        conn.execute(
            "INSERT INTO veto_records (veto_timestamp, dna_id, dna_fitness, reason, issuer, metadata) VALUES (?,?,?,?,?,?)",
            (ts_old, "dna2", 1.0, "stale_reason", "twin", "{}"),
        )
        conn.commit()

    mod_path = Path(__file__).resolve().parents[1] / "lumina_os" / "frontend" / "monitoring_dashboard.py"
    spec = importlib.util.spec_from_file_location("_weekly_veto_test_mod", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    count, top = mod.weekly_veto_summary(state)
    assert count == 1
    assert top and top[0][0] == "too_risky"
