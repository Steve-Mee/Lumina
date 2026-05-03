from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from backend import evolution_endpoints as ep
from lumina_core.governance import RealPromotionPayload


@pytest.fixture(autouse=True)
def _reset_evolution_security_module() -> Any:
    ep.set_security_module(None)
    yield
    ep.set_security_module(None)


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
        ep._verify_api_key("wrong", require_admin=True)
    assert exc.value.status_code == 401


def test_security_module_requires_admin_for_mutations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_MODE", "real")

    class _Cfg:
        admin_role_required = True

    class _AK:
        def verify_api_key(self, key: str):
            if key == "admin-key":
                return {"name": "ops", "role": "admin", "enabled": True}
            if key == "user-key":
                return {"name": "ro", "role": "user", "enabled": True}
            return None

    class _Audit:
        def log_auth_attempt(self, *args: object, **kwargs: object) -> None:
            return None

        def log_unauthorized_access(self, *args: object, **kwargs: object) -> None:
            return None

    ep.set_security_module({"config": _Cfg(), "api_key": _AK(), "audit_log": _Audit()})
    ep._verify_api_key("admin-key", require_admin=True)
    with pytest.raises(HTTPException) as exc:
        ep._verify_api_key("user-key", require_admin=True)
    assert exc.value.status_code == 403


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


def _prepare_real_approve_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_MODE", "real")
    monkeypatch.setattr(ep, "_verify_api_key", lambda _key, require_admin=False: None)
    monkeypatch.setattr(
        ep,
        "_load_proposals",
        lambda: [
            {
                "hash": "h1",
                "status": "proposed",
                "challengers": [{"name": "c1", "hyperparam_suggestion": {"alpha": 1}}],
            }
        ],
    )
    monkeypatch.setattr(ep, "_load_decisions", lambda: {})
    monkeypatch.setattr(ep.TRADING_CONSTITUTION, "audit", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        ep,
        "check_promotion_readiness",
        lambda **kwargs: SimpleNamespace(ok=True, message=lambda: "ok"),
    )


def test_approve_rejects_real_when_human_approval_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_real_approve_context(monkeypatch)
    req = ep.ApproveRequest(hash="h1", challenger_name="c1", require_human_approval=False)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ep.approve_proposal(req, x_api_key="admin-key"))

    assert exc.value.status_code == 422
    assert "cannot be disabled" in str(exc.value.detail)


def test_approve_rejects_real_when_signed_payload_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_real_approve_context(monkeypatch)
    req = ep.ApproveRequest(hash="h1", challenger_name="c1", require_human_approval=True)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ep.approve_proposal(req, x_api_key="admin-key"))

    assert exc.value.status_code == 422
    assert "signed promotion payload" in str(exc.value.detail)


def test_approve_rejects_real_when_payload_hash_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    _prepare_real_approve_context(monkeypatch)
    payload = RealPromotionPayload(
        dna_hash="other_hash",
        target_mode="real",
        dna_content_digest="a" * 64,
        promotion_epoch="gen:1:other",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    req = ep.ApproveRequest(
        hash="h1",
        challenger_name="c1",
        require_human_approval=True,
        promotion_payload=payload,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(ep.approve_proposal(req, x_api_key="admin-key"))

    assert exc.value.status_code == 422
    assert "dna_hash does not match" in str(exc.value.detail)
