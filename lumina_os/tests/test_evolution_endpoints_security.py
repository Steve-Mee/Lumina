from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from backend import evolution_endpoints as ep


def test_verify_api_key_fail_closed_when_protected_mode_and_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_MODE", "real")
    monkeypatch.setattr(ep, "_DASHBOARD_API_KEY", "")
    with pytest.raises(HTTPException) as exc:
        ep._verify_api_key(None)
    assert exc.value.status_code == 503


def test_verify_api_key_rejects_invalid_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_MODE", "real")
    monkeypatch.setattr(ep, "_DASHBOARD_API_KEY", "secret-key")
    with pytest.raises(HTTPException) as exc:
        ep._verify_api_key("wrong")
    assert exc.value.status_code == 401


def test_append_decision_is_hash_chained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    decisions_file = tmp_path / "evolution_decisions.jsonl"
    monkeypatch.setattr(ep, "_EVOLUTION_DECISIONS", decisions_file)

    ep._append_decision({"hash": "a1", "decision": "approved"})
    ep._append_decision({"hash": "b2", "decision": "rejected"})

    lines = decisions_file.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["prev_hash"] == "GENESIS"
    assert first["entry_hash"]
    assert second["prev_hash"] == first["entry_hash"]
    assert second["entry_hash"]
