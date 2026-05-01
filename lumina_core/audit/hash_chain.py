from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical_payload(entry: dict[str, Any]) -> str:
    payload = {k: v for k, v in entry.items() if k not in {"prev_hash", "entry_hash"}}
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _latest_entry_hash(path: Path) -> str:
    if not path.exists():
        return "GENESIS"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "GENESIS"
    for raw in reversed(lines):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return "GENESIS"
        h = obj.get("entry_hash")
        return str(h) if h else "GENESIS"
    return "GENESIS"


def append_hash_chained_jsonl(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """Append record with prev_hash + entry_hash to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    prev_hash = _latest_entry_hash(path)
    canonical = _canonical_payload(entry)
    digest = hashlib.sha256(f"{prev_hash}|{canonical}".encode("utf-8")).hexdigest()
    chained = dict(entry)
    chained["prev_hash"] = prev_hash
    chained["entry_hash"] = digest
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(chained, ensure_ascii=True) + "\n")
    return chained


def validate_hash_chain(path: Path) -> tuple[bool, str]:
    """Validate the full chain and return (ok, message)."""
    if not path.exists():
        return True, "missing_file_treated_as_empty"
    prev = "GENESIS"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return False, f"io_error:{exc}"
    for idx, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return False, f"json_parse_error_line_{idx}"
        recorded_prev = str(entry.get("prev_hash", ""))
        recorded_hash = str(entry.get("entry_hash", ""))
        if recorded_prev != prev:
            return False, f"prev_hash_mismatch_line_{idx}"
        canonical = _canonical_payload(entry)
        expected = hashlib.sha256(f"{recorded_prev}|{canonical}".encode("utf-8")).hexdigest()
        if recorded_hash != expected:
            return False, f"entry_hash_mismatch_line_{idx}"
        prev = recorded_hash
    return True, "ok"
