from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.audit.hash_chain import append_hash_chained_jsonl, validate_hash_chain


@pytest.mark.unit
def test_hash_chain_appends_prev_and_entry_hash(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    first = append_hash_chained_jsonl(path, {"event": "a", "value": 1})
    second = append_hash_chained_jsonl(path, {"event": "b", "value": 2})

    assert first["prev_hash"] == "GENESIS"
    assert first["entry_hash"]
    assert second["prev_hash"] == first["entry_hash"]
    assert second["entry_hash"]


@pytest.mark.unit
def test_validate_hash_chain_detects_tamper(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    append_hash_chained_jsonl(path, {"event": "a"})
    append_hash_chained_jsonl(path, {"event": "b"})

    lines = path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[1])
    record["event"] = "tampered"
    lines[1] = json.dumps(record)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ok, msg = validate_hash_chain(path)
    assert ok is False
    assert "entry_hash_mismatch" in msg
