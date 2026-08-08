"""M7: Telegram advance TTL hygiene + Phase Hub public DTO polish."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from lumina_core.maturity.advance_policy import (
    confirm_telegram_advance,
    reissue_telegram_advance,
    _notify_telegram_advance,
)
from lumina_core.maturity.continuum import (
    clear_expired_pending_advance,
    load_continuum,
    mark_phase_completed,
    pending_advance_expired,
    pending_advance_public,
    pending_advance_remaining_sec,
    save_continuum,
    set_advance_mode,
    set_pending_advance,
)
from lumina_core.maturity.phase_specs import hub_payload


@pytest.mark.unit
def test_pending_advance_remaining_sec_active(tmp_path: Path) -> None:
    data = set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening", ttl_sec=3600)
    pending = data["pending_advance"]
    rem = pending_advance_remaining_sec(pending)
    assert rem is not None
    assert 3500 <= rem <= 3600
    assert pending_advance_expired(pending) is False


@pytest.mark.unit
def test_pending_advance_remaining_sec_expired() -> None:
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    pending = {
        "from": "a",
        "to": "b",
        "telegram_token": "x",
        "expires_at": past,
        "ttl_sec": 300,
    }
    assert pending_advance_remaining_sec(pending) == 0
    assert pending_advance_expired(pending) is True


@pytest.mark.unit
def test_pending_advance_public_no_token_leak(tmp_path: Path) -> None:
    data = set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening", ttl_sec=1800)
    pending = data["pending_advance"]
    pub = pending_advance_public(pending)
    assert pub is not None
    assert "telegram_token" not in pub
    assert pub["has_token"] is True
    assert pub["status"] == "active"
    assert pub["expired"] is False
    assert isinstance(pub["remaining_sec"], int)
    assert pub["remaining_sec"] > 0
    assert pub["from"] == "birth"
    assert pub["to"] == "awakening"


@pytest.mark.unit
def test_pending_advance_public_expired_status() -> None:
    past = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    pending = {
        "from": "birth",
        "to": "awakening",
        "telegram_token": "secret-token-value",
        "expires_at": past,
        "ttl_sec": 300,
    }
    pub = pending_advance_public(pending)
    assert pub is not None
    assert pub["expired"] is True
    assert pub["status"] == "expired"
    assert pub["remaining_sec"] == 0
    assert "telegram_token" not in pub
    assert "secret" not in str(pub)


@pytest.mark.unit
def test_hub_payload_clears_expired_pending(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "telegram")
    data = set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening", ttl_sec=300)
    pending = dict(data["pending_advance"])
    continuum = load_continuum(tmp_path)
    continuum["pending_advance"] = {
        **pending,
        "expires_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    }
    save_continuum(tmp_path, continuum)

    hub = hub_payload(tmp_path)
    assert hub.get("pending_advance") is None
    assert load_continuum(tmp_path).get("pending_advance") is None
    ta = hub.get("telegram_advance") or {}
    assert ta.get("mode_is_telegram") is True
    assert ta.get("reissue_available") is True
    assert int(ta.get("configured_ttl_sec") or 0) >= 300


@pytest.mark.unit
def test_hub_payload_embeds_remaining_sec(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "telegram")
    set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening", ttl_sec=7200)
    hub = hub_payload(tmp_path)
    pa = hub.get("pending_advance")
    assert isinstance(pa, dict)
    assert "telegram_token" not in pa
    assert pa.get("status") == "active"
    rem = pa.get("remaining_sec")
    assert isinstance(rem, int)
    assert 7000 <= rem <= 7200
    ta = hub.get("telegram_advance") or {}
    assert ta.get("pending") is not None
    assert ta.get("pending", {}).get("remaining_sec") == rem


@pytest.mark.unit
def test_reissue_returns_remaining_sec(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "telegram")
    with patch("lumina_core.maturity.advance_policy._notify_telegram_advance"):
        result = reissue_telegram_advance(tmp_path)
    assert result["ok"] is True
    assert result.get("status") == "active"
    assert result.get("has_token") is True
    assert isinstance(result.get("remaining_sec"), int)
    assert result["remaining_sec"] > 0
    assert result.get("expires_at")
    assert "remaining" in str(result.get("message") or "").lower() or result.get("expires_at")


@pytest.mark.unit
def test_reissue_dedupe_key_includes_expires() -> None:
    """Reissue must not share dedupe with prior token (expires_at in key)."""
    keys: list[str] = []

    def capture_notify(ev, workspace_root=None):
        keys.append(str(getattr(ev, "dedupe_key", "") or ""))

    with patch(
        "lumina_core.notifications.attention_notifier.notify_attention",
        side_effect=capture_notify,
    ):
        _notify_telegram_advance(
            Path("."),
            "birth",
            "awakening",
            "token-aaa",
            expires_at="2026-08-07T12:00:00+00:00",
            ttl_sec=3600,
        )
        _notify_telegram_advance(
            Path("."),
            "birth",
            "awakening",
            "token-bbb",
            expires_at="2026-08-08T12:00:00+00:00",
            ttl_sec=3600,
        )
    assert len(keys) == 2
    assert keys[0] != keys[1]
    assert "phase_advance_request:birth:awakening:" in keys[0]
    assert "phase_advance_request:birth:awakening:" in keys[1]


@pytest.mark.unit
def test_confirm_clears_and_clear_expired_idempotent(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    data = set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening", ttl_sec=600)
    token = str(data["pending_advance"]["telegram_token"])
    ok = confirm_telegram_advance(tmp_path, token=token)
    assert ok["ok"] is True
    # Second clear on empty is not_expired / no_pending
    again = clear_expired_pending_advance(tmp_path)
    assert again["cleared"] is False
    assert again["reason"] == "no_pending"
