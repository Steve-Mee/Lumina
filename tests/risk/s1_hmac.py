"""Shared HMAC LIVE_RELEASE records for S1 tests and the mutation kill battery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from lumina_core.risk.live_release import (
    PURPOSE_LIVE,
    SCHEMA_VERSION,
    compute_live_release_mac,
)

TEST_SECRET = "s1-live-release-secret-key"
ADR_PATH = "docs/adr/0061-sim-whitelist-and-live-release.md"
ADR_SHA = "a" * 64


def signed_live_release(
    secret: str = TEST_SECRET,
    *,
    now: datetime | None = None,
    nonce: str = "nonce-16-chars-xx",
    **overrides: object,
) -> dict[str, Any]:
    clock = now if now is not None else datetime.now(timezone.utc)
    approved = clock.astimezone(timezone.utc).replace(microsecond=0)
    expires = approved + timedelta(days=1)
    record: dict[str, Any] = {
        "enabled": True,
        "adr_path": ADR_PATH,
        "adr_sha256": ADR_SHA,
        "approved_by": "steve.operator",
        "approved_at_utc": approved.isoformat().replace("+00:00", "Z"),
        "expires_at_utc": expires.isoformat().replace("+00:00", "Z"),
        "nonce": nonce,
        "purpose": PURPOSE_LIVE,
        "schema_version": SCHEMA_VERSION,
        "mac": "",
    }
    record.update(overrides)
    if "mac" not in overrides:
        record["mac"] = compute_live_release_mac(record, secret.encode("utf-8"))
    return record
