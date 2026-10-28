"""UTC timestamps for KEEP evolution fabric. Birth-v1 fitness search is archived."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
