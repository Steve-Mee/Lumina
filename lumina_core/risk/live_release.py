"""HMAC-signed LIVE_RELEASE artifact verified inside the live Risk Core (ADR-0061).

The secret is read from env ``LUMINA_LIVE_RELEASE_SECRET`` only. It is never
logged and must never live in the repo, yaml, or fabric.json. A valid
signature does not enable live orders in S1 (``live_account_path_closed_s1``).
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import threading
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, Final

from lumina_core.risk.s1_events import s1_reject_event_data

logger = logging.getLogger("lumina.risk.live_release")

SECRET_ENV: Final[str] = "LUMINA_LIVE_RELEASE_SECRET"
MIN_SECRET_LEN: Final[int] = 16
MAC_HEX_LEN: Final[int] = 64
SCHEMA_VERSION: Final[str] = "live_release.v1"
PURPOSE_LIVE: Final[str] = "live_enablement"
PURPOSE_WHITELIST_WIDEN: Final[str] = "sim_whitelist_widen"
LEGAL_PURPOSES: Final[frozenset[str]] = frozenset({PURPOSE_LIVE, PURPOSE_WHITELIST_WIDEN})
MAX_CLOCK_SKEW: Final[timedelta] = timedelta(minutes=5)
MAX_TTL: Final[timedelta] = timedelta(days=7)
ADR_PATH_RE: Final[re.Pattern[str]] = re.compile(r"^docs/adr/\d{4}-[a-z0-9-]+\.md$")
SHA256_HEX_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")

LIVE_RELEASE_SECRET_MISSING: Final[str] = "live_release_secret_missing"
LIVE_RELEASE_RECORD_MISSING: Final[str] = "live_release_record_missing"
LIVE_RELEASE_DISABLED: Final[str] = "live_release_disabled"
LIVE_RELEASE_HMAC_REQUIRED: Final[str] = "live_release_hmac_required"
LIVE_RELEASE_MAC_INVALID: Final[str] = "live_release_mac_invalid"
LIVE_RELEASE_MAC_MISMATCH: Final[str] = "live_release_mac_mismatch"
LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN: Final[str] = "live_release_agent_approver_forbidden"
LIVE_RELEASE_ADR_REQUIRED: Final[str] = "live_release_adr_required"
LIVE_RELEASE_ADR_HASH_INVALID: Final[str] = "live_release_adr_hash_invalid"
LIVE_RELEASE_EXPIRED: Final[str] = "live_release_expired"
LIVE_RELEASE_CLOCK_SKEW: Final[str] = "live_release_clock_skew"
LIVE_RELEASE_WINDOW_INVALID: Final[str] = "live_release_window_invalid"
LIVE_RELEASE_REPLAY: Final[str] = "live_release_replay"
LIVE_RELEASE_NONCE_INVALID: Final[str] = "live_release_nonce_invalid"
LIVE_RELEASE_PURPOSE_INVALID: Final[str] = "live_release_purpose_invalid"
LIVE_RELEASE_TIMESTAMP_NOT_UTC: Final[str] = "live_release_timestamp_not_utc"
LIVE_RELEASE_HMAC_OK: Final[str] = "live_release_hmac_ok"
LIVE_ACCOUNT_PATH_CLOSED_S1: Final[str] = "live_account_path_closed_s1"
LIVE_RELEASE_REQUIRED: Final[str] = "live_release_required"

_AGENT_MARKERS: Final[tuple[str, ...]] = (
    "agent",
    "research",
    "hypothesis",
    "lumina_research",
    "twin",
    "swarm",
    "reflector",
    "birth",
    "promotion",
    "validation_agent",
    "research_bridge",
)

_NONCES: set[str] = set()
_NONCE_LOCK = threading.Lock()


def log_live_reject(*, reason: str, agent_id: str = "", approved_by: str = "") -> None:
    logger.error(
        "s1.live_release.reject",
        extra={
            "event_data": s1_reject_event_data(
                event="s1.live_release.reject",
                reason=reason,
                agent_id=agent_id,
                approved_by=approved_by,
            )
        },
    )


def _secret_bytes() -> bytes | None:
    raw = os.environ.get(SECRET_ENV)
    if raw is None:
        return None
    text = str(raw).strip()
    if len(text) < MIN_SECRET_LEN:
        return None
    return text.encode("utf-8")


def _as_mapping(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    if not isinstance(record, Mapping):
        return None
    return {str(key): record[key] for key in record}


def _parse_utc(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _iso_z(moment: datetime) -> str:
    utc = moment.astimezone(timezone.utc).replace(microsecond=0)
    return utc.isoformat().replace("+00:00", "Z")


def _bool_enabled(value: object) -> bool:
    """Only the JSON/Python boolean True enables. Strings never enable."""
    return value is True


def canonical_live_release_payload(record: Mapping[str, Any]) -> bytes:
    """Stable HMAC message. ``mac`` is excluded."""
    approved_at = _parse_utc(record.get("approved_at_utc"))
    expires_at = _parse_utc(record.get("expires_at_utc"))
    # Insertion order is deliberately not alphabetical so sort_keys=True is
    # load-bearing: HMAC bytes must not follow dict order.
    body = {
        "enabled": bool(_bool_enabled(record.get("enabled"))),
        "nonce": str(record.get("nonce") or "").strip(),
        "purpose": str(record.get("purpose") or "").strip(),
        "schema_version": str(record.get("schema_version") or "").strip(),
        "approved_by": str(record.get("approved_by") or "").strip(),
        "adr_path": str(record.get("adr_path") or "").strip(),
        "adr_sha256": str(record.get("adr_sha256") or "").strip().lower(),
        "approved_at_utc": _iso_z(approved_at) if approved_at is not None else "",
        "expires_at_utc": _iso_z(expires_at) if expires_at is not None else "",
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_live_release_mac(record: Mapping[str, Any], secret: bytes) -> str:
    digest = hmac.new(secret, canonical_live_release_payload(record), "sha256").hexdigest()
    return digest


def _is_agent_approver(approved_by: str) -> bool:
    token = approved_by.strip()
    if len(token) < 2:
        return True
    folded = token.casefold().replace("-", "_")
    return any(marker in folded for marker in _AGENT_MARKERS)


def _mac_hex_ok(mac: str) -> bool:
    if len(mac) != MAC_HEX_LEN:
        return False
    try:
        int(mac, 16)
    except ValueError:
        return False
    return True


def _consume_nonce(nonce: str) -> bool:
    """Return True if the nonce is new and now consumed."""
    token = str(nonce or "").strip()
    if len(token) < 16:
        return False
    with _NONCE_LOCK:
        if token in _NONCES:
            return False
        _NONCES.add(token)
        return True


def nonce_was_used(nonce: str) -> bool:
    with _NONCE_LOCK:
        return str(nonce or "").strip() in _NONCES


def reset_live_release_nonces_for_tests() -> None:
    """Test hook. Production callers get an empty reset that still fail-closes nothing else."""
    with _NONCE_LOCK:
        _NONCES.clear()


def verify_live_release(
    record: Mapping[str, Any] | None,
    *,
    expected_purpose: str = PURPOSE_LIVE,
    now: object | None = None,
    agent_id: str = "",
) -> tuple[bool, str]:
    """Cryptographic + human-ADR checks. Does not enable a live account path."""
    secret = _secret_bytes()
    if secret is None:
        log_live_reject(reason=LIVE_RELEASE_SECRET_MISSING, agent_id=agent_id)
        return False, LIVE_RELEASE_SECRET_MISSING
    payload = _as_mapping(record)
    if payload is None:
        log_live_reject(reason=LIVE_RELEASE_RECORD_MISSING, agent_id=agent_id)
        return False, LIVE_RELEASE_RECORD_MISSING
    if _bool_enabled(payload.get("enabled")) is not True:
        log_live_reject(reason=LIVE_RELEASE_DISABLED, agent_id=agent_id)
        return False, LIVE_RELEASE_DISABLED
    mac = str(payload.get("mac") or "").strip().lower()
    if not mac:
        log_live_reject(reason=LIVE_RELEASE_HMAC_REQUIRED, agent_id=agent_id)
        return False, LIVE_RELEASE_HMAC_REQUIRED
    if not _mac_hex_ok(mac):
        log_live_reject(reason=LIVE_RELEASE_MAC_INVALID, agent_id=agent_id)
        return False, LIVE_RELEASE_MAC_INVALID
    purpose = str(payload.get("purpose") or "").strip()
    if purpose not in LEGAL_PURPOSES or purpose != str(expected_purpose):
        log_live_reject(reason=LIVE_RELEASE_PURPOSE_INVALID, agent_id=agent_id)
        return False, LIVE_RELEASE_PURPOSE_INVALID
    schema = str(payload.get("schema_version") or "").strip()
    if schema != SCHEMA_VERSION:
        log_live_reject(reason=LIVE_RELEASE_PURPOSE_INVALID, agent_id=agent_id)
        return False, LIVE_RELEASE_PURPOSE_INVALID
    approved_by = str(payload.get("approved_by") or "").strip()
    if _is_agent_approver(approved_by):
        log_live_reject(
            reason=LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN,
            agent_id=agent_id,
            approved_by=approved_by,
        )
        return False, LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN
    adr_path = str(payload.get("adr_path") or "").strip()
    if not ADR_PATH_RE.match(adr_path):
        log_live_reject(reason=LIVE_RELEASE_ADR_REQUIRED, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_ADR_REQUIRED
    adr_sha = str(payload.get("adr_sha256") or "").strip().lower()
    if not SHA256_HEX_RE.match(adr_sha):
        log_live_reject(reason=LIVE_RELEASE_ADR_HASH_INVALID, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_ADR_HASH_INVALID
    approved_at = _parse_utc(payload.get("approved_at_utc"))
    expires_at = _parse_utc(payload.get("expires_at_utc"))
    if approved_at is None or expires_at is None:
        log_live_reject(reason=LIVE_RELEASE_TIMESTAMP_NOT_UTC, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_TIMESTAMP_NOT_UTC
    if now is not None:
        if not isinstance(now, datetime) or now.tzinfo is None:
            log_live_reject(
                reason=LIVE_RELEASE_TIMESTAMP_NOT_UTC,
                agent_id=agent_id,
                approved_by=approved_by,
            )
            return False, LIVE_RELEASE_TIMESTAMP_NOT_UTC
        clock = now.astimezone(timezone.utc)
    else:
        clock = datetime.now(timezone.utc)
    if approved_at - clock > MAX_CLOCK_SKEW:
        log_live_reject(reason=LIVE_RELEASE_CLOCK_SKEW, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_CLOCK_SKEW
    if expires_at <= clock:
        log_live_reject(reason=LIVE_RELEASE_EXPIRED, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_EXPIRED
    if expires_at <= approved_at or (expires_at - approved_at) > MAX_TTL:
        log_live_reject(reason=LIVE_RELEASE_WINDOW_INVALID, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_WINDOW_INVALID
    expected = compute_live_release_mac(payload, secret)
    if not hmac.compare_digest(expected, mac):
        log_live_reject(reason=LIVE_RELEASE_MAC_MISMATCH, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_MAC_MISMATCH
    nonce = str(payload.get("nonce") or "").strip()
    if len(nonce) < 16:
        log_live_reject(reason=LIVE_RELEASE_NONCE_INVALID, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_NONCE_INVALID
    if not _consume_nonce(nonce):
        log_live_reject(reason=LIVE_RELEASE_REPLAY, agent_id=agent_id, approved_by=approved_by)
        return False, LIVE_RELEASE_REPLAY
    return True, LIVE_RELEASE_HMAC_OK


def admit_live_orders(
    record: Mapping[str, Any] | None,
    *,
    now: object | None = None,
    agent_id: str = "",
) -> tuple[bool, str]:
    """S1: live account path stays closed even when HMAC verifies."""
    ok, reason = verify_live_release(
        record,
        expected_purpose=PURPOSE_LIVE,
        now=now,
        agent_id=agent_id,
    )
    if ok is not True:
        return False, reason
    log_live_reject(reason=LIVE_ACCOUNT_PATH_CLOSED_S1, agent_id=agent_id)
    return False, LIVE_ACCOUNT_PATH_CLOSED_S1


def live_release_from_engine(engine: object | None) -> dict[str, Any] | None:
    if engine is None:
        return None
    config = getattr(engine, "config", None)
    if config is None:
        return None
    raw = getattr(config, "live_release_payload", None)
    if isinstance(raw, Mapping):
        return dict(raw)
    return None


__all__ = [
    "ADR_PATH_RE",
    "LEGAL_PURPOSES",
    "LIVE_ACCOUNT_PATH_CLOSED_S1",
    "LIVE_RELEASE_ADR_HASH_INVALID",
    "LIVE_RELEASE_ADR_REQUIRED",
    "LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN",
    "LIVE_RELEASE_CLOCK_SKEW",
    "LIVE_RELEASE_DISABLED",
    "LIVE_RELEASE_EXPIRED",
    "LIVE_RELEASE_HMAC_OK",
    "LIVE_RELEASE_HMAC_REQUIRED",
    "LIVE_RELEASE_MAC_INVALID",
    "LIVE_RELEASE_MAC_MISMATCH",
    "LIVE_RELEASE_NONCE_INVALID",
    "LIVE_RELEASE_PURPOSE_INVALID",
    "LIVE_RELEASE_RECORD_MISSING",
    "LIVE_RELEASE_REPLAY",
    "LIVE_RELEASE_REQUIRED",
    "LIVE_RELEASE_SECRET_MISSING",
    "LIVE_RELEASE_TIMESTAMP_NOT_UTC",
    "LIVE_RELEASE_WINDOW_INVALID",
    "MAC_HEX_LEN",
    "MAX_CLOCK_SKEW",
    "MAX_TTL",
    "MIN_SECRET_LEN",
    "PURPOSE_LIVE",
    "PURPOSE_WHITELIST_WIDEN",
    "SCHEMA_VERSION",
    "SECRET_ENV",
    "admit_live_orders",
    "canonical_live_release_payload",
    "compute_live_release_mac",
    "live_release_from_engine",
    "log_live_reject",
    "nonce_was_used",
    "reset_live_release_nonces_for_tests",
    "verify_live_release",
]
