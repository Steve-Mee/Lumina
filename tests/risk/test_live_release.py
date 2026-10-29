from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lumina_core.risk.live_release import (
    LIVE_ACCOUNT_PATH_CLOSED_S1,
    LIVE_RELEASE_ADR_HASH_INVALID,
    LIVE_RELEASE_ADR_REQUIRED,
    LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN,
    LIVE_RELEASE_CLOCK_SKEW,
    LIVE_RELEASE_DISABLED,
    LIVE_RELEASE_EXPIRED,
    LIVE_RELEASE_HMAC_REQUIRED,
    LIVE_RELEASE_MAC_INVALID,
    LIVE_RELEASE_MAC_MISMATCH,
    LIVE_RELEASE_NONCE_INVALID,
    LIVE_RELEASE_PURPOSE_INVALID,
    LIVE_RELEASE_RECORD_MISSING,
    LIVE_RELEASE_REPLAY,
    LIVE_RELEASE_SECRET_MISSING,
    LIVE_RELEASE_TIMESTAMP_NOT_UTC,
    LIVE_RELEASE_WINDOW_INVALID,
    SECRET_ENV,
    admit_live_orders,
    reset_live_release_nonces_for_tests,
    verify_live_release,
)
from tests.risk.s1_hmac import TEST_SECRET, signed_live_release


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    reset_live_release_nonces_for_tests()


@pytest.mark.unit
@pytest.mark.safety_gate
def test_enabled_false_denies_real() -> None:
    record = signed_live_release(enabled=False)
    ok, reason = verify_live_release(record)
    assert ok is False
    assert reason == LIVE_RELEASE_DISABLED


@pytest.mark.unit
@pytest.mark.safety_gate
def test_hash_without_mac_is_refused() -> None:
    record = signed_live_release(mac="")
    ok, reason = verify_live_release(record)
    assert ok is False
    assert reason == LIVE_RELEASE_HMAC_REQUIRED


@pytest.mark.unit
def test_wrong_mac_is_rejected() -> None:
    record = signed_live_release(mac="b" * 64)
    ok, reason = verify_live_release(record)
    assert ok is False
    assert reason == LIVE_RELEASE_MAC_MISMATCH


@pytest.mark.unit
def test_truncated_mac_is_rejected() -> None:
    record = signed_live_release()
    record["mac"] = record["mac"][:32]
    ok, reason = verify_live_release(record)
    assert ok is False
    assert reason == LIVE_RELEASE_MAC_INVALID


@pytest.mark.unit
def test_missing_secret_env_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRET_ENV, raising=False)
    ok, reason = verify_live_release(signed_live_release())
    assert ok is False
    assert reason == LIVE_RELEASE_SECRET_MISSING


@pytest.mark.unit
def test_short_secret_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, "short")
    ok, reason = verify_live_release(signed_live_release())
    assert ok is False
    assert reason == LIVE_RELEASE_SECRET_MISSING


@pytest.mark.unit
@pytest.mark.safety_gate
def test_valid_hmac_still_closes_live_orders() -> None:
    record = signed_live_release()
    ok, reason = verify_live_release(record)
    assert ok is True
    reset_live_release_nonces_for_tests()
    allowed, closed = admit_live_orders(signed_live_release(nonce="nonce-16-chars-yy"))
    assert allowed is False
    assert closed == LIVE_ACCOUNT_PATH_CLOSED_S1


@pytest.mark.unit
def test_agent_approver_is_forbidden() -> None:
    record = signed_live_release(approved_by="research_bridge")
    ok, reason = verify_live_release(record)
    assert ok is False
    assert reason == LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN


@pytest.mark.unit
def test_missing_record_and_adr_and_purpose_and_nonce() -> None:
    assert verify_live_release(None)[1] == LIVE_RELEASE_RECORD_MISSING
    assert verify_live_release(signed_live_release(adr_path="not-an-adr"))[1] == LIVE_RELEASE_ADR_REQUIRED
    assert verify_live_release(signed_live_release(adr_sha256="nope"))[1] == LIVE_RELEASE_ADR_HASH_INVALID
    assert verify_live_release(signed_live_release(purpose="other"))[1] == LIVE_RELEASE_PURPOSE_INVALID
    assert verify_live_release(signed_live_release(schema_version="v0"))[1] == LIVE_RELEASE_PURPOSE_INVALID
    assert verify_live_release(signed_live_release(nonce="short"))[1] == LIVE_RELEASE_NONCE_INVALID


@pytest.mark.unit
def test_replay_is_rejected() -> None:
    record = signed_live_release(nonce="replay-nonce-0001")
    assert verify_live_release(record)[0] is True
    again = signed_live_release(nonce="replay-nonce-0001")
    ok, reason = verify_live_release(again)
    assert ok is False
    assert reason == LIVE_RELEASE_REPLAY


@pytest.mark.unit
def test_clock_skew_and_expiry_and_window_and_naive_ts() -> None:
    now = datetime.now(timezone.utc)
    future = signed_live_release(now=now + timedelta(minutes=30))
    ok, reason = verify_live_release(future, now=now)
    assert ok is False
    assert reason == LIVE_RELEASE_CLOCK_SKEW

    expired = signed_live_release(
        now=now,
        expires_at_utc=(now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
    )
    ok, reason = verify_live_release(expired, now=now)
    assert ok is False
    assert reason == LIVE_RELEASE_EXPIRED

    wide = signed_live_release(
        now=now,
        expires_at_utc=(now + timedelta(days=8)).isoformat().replace("+00:00", "Z"),
    )
    ok, reason = verify_live_release(wide, now=now)
    assert ok is False
    assert reason == LIVE_RELEASE_WINDOW_INVALID

    naive = signed_live_release(approved_at_utc="2026-10-29T00:00:00")
    ok, reason = verify_live_release(naive, now=now)
    assert ok is False
    assert reason == LIVE_RELEASE_TIMESTAMP_NOT_UTC
