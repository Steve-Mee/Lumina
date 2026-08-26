"""Organism schema namespace — never ALTER core tables (K15)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from lumina_core.state.state_manager import safe_sqlite_connect

_COL = re.compile(r"^org_[a-z0-9_]{1,40}$")
_TYPES = frozenset({"TEXT", "INTEGER", "REAL", "JSON"})


def extensions_db(workspace: Path | str) -> Path:
    path = Path(workspace) / "state" / "organism_extensions.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def validate_columns(columns: list[dict[str, Any]]) -> list[str]:
    fails: list[str] = []
    for col in columns:
        name = str(col.get("name") or "")
        typ = str(col.get("type") or "").upper()
        if not _COL.match(name):
            fails.append(f"illegal_name:{name}")
        if typ not in _TYPES:
            fails.append(f"illegal_type:{typ}")
    return fails


def ledger_hash(columns: list[dict[str, Any]]) -> str:
    canonical = json.dumps(columns, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def ensure_base(workspace: Path | str) -> None:
    db = extensions_db(workspace)
    with safe_sqlite_connect(db) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_ledger (
                version INTEGER PRIMARY KEY,
                ledger_hash TEXT NOT NULL,
                proposal_id TEXT NOT NULL,
                applied_at TEXT NOT NULL,
                revert_ddl TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS organism_facts (
                entity_key TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )
            """
        )
        con.commit()


def loaded_ledger_hash(workspace: Path | str) -> str:
    ensure_base(workspace)
    db = extensions_db(workspace)
    with safe_sqlite_connect(db) as con:
        row = con.execute(
            "SELECT ledger_hash FROM schema_ledger ORDER BY version DESC LIMIT 1"
        ).fetchone()
    return str(row[0]) if row else ""


def apply_extension(
    workspace: Path | str,
    *,
    proposal_id: str,
    columns: list[dict[str, Any]],
    capital_mode: str = "sim",
) -> dict[str, Any]:
    from lumina_core.code_evolution.runtime_role import is_real_like_capital

    if is_real_like_capital(capital_mode):
        return {"ok": False, "reason": "real_blocked"}
    fails = validate_columns(columns)
    if fails:
        return {"ok": False, "reason": "invalid_columns", "fail_reasons": fails}
    ensure_base(workspace)
    db = extensions_db(workspace)
    digest = ledger_hash(columns)
    revert: list[str] = []
    with safe_sqlite_connect(db) as con:
        existing = {str(r[1]) for r in con.execute("PRAGMA table_info(organism_facts)").fetchall()}
        for col in columns:
            name = str(col["name"])
            typ = str(col["type"]).upper()
            sql_type = "TEXT" if typ == "JSON" else typ
            if name in existing:
                continue
            con.execute(f"ALTER TABLE organism_facts ADD COLUMN {name} {sql_type}")
            revert.append(name)
        con.execute(
            """
            INSERT INTO schema_ledger (ledger_hash, proposal_id, applied_at, revert_ddl)
            VALUES (?, ?, datetime('now'), ?)
            """,
            (digest, proposal_id, json.dumps(revert)),
        )
        con.commit()
    return {"ok": True, "ledger_hash": digest, "added": revert}


def overlay_schema_ok(*, expected: str, loaded: str, requires_org_cols: bool) -> bool:
    if not requires_org_cols:
        return True
    return str(expected or "") == str(loaded or "") and bool(expected)
