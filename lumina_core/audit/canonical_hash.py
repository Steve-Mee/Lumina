from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_HASH = "GENESIS"
AUDIT_SCHEMA_VERSION = "lumina_audit_v1"
_HASH_FIELDS = frozenset({"prev_hash", "entry_hash", "hash"})


def strip_hash_fields(entry: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entry.items() if k not in _HASH_FIELDS}


def canonical_json_for_entry_hash(entry: dict[str, Any]) -> str:
    payload = strip_hash_fields(entry)
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def compute_entry_hash(prev_hash: str, entry: dict[str, Any]) -> str:
    canonical = canonical_json_for_entry_hash(entry)
    return hashlib.sha256(f"{prev_hash}|{canonical}".encode("utf-8")).hexdigest()
