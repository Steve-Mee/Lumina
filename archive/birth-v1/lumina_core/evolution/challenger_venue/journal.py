"""Hash-chained challenger journal + replay digest (K7)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lumina_core.evolution.challenger_venue.dna_namespace import challenger_state_root
from lumina_core.state.state_manager import safe_append_jsonl


def journal_path(workspace: Path | str) -> Path:
    root = challenger_state_root(workspace)
    root.mkdir(parents=True, exist_ok=True)
    return root / "journal.jsonl"


def append_journal(workspace: Path | str, record: dict[str, Any]) -> dict[str, Any]:
    return safe_append_jsonl(journal_path(workspace), dict(record), hash_chain=True)


def load_journal(workspace: Path | str) -> list[dict[str, Any]]:
    path = journal_path(workspace)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                rows.append(raw)
    except OSError:
        return []
    return rows


def replay_digest(rows: list[dict[str, Any]]) -> str:
    material: list[dict[str, Any]] = []
    for row in rows:
        material.append(
            {
                k: row.get(k)
                for k in (
                    "intent_id",
                    "side",
                    "qty",
                    "fill_price",
                    "pnl",
                    "overlay_id",
                    "dna_hash",
                    "reason",
                )
                if k in row
            }
        )
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_and_digest(workspace: Path | str, record: dict[str, Any]) -> tuple[dict[str, Any], str]:
    written = append_journal(workspace, record)
    digest = replay_digest(load_journal(workspace))
    return written, digest
