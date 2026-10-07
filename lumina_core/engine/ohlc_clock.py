"""UTC clock for NT bar timestamps. Naive wall clocks are rejected."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


def utc_from_unix_ms(ms: int | float | None) -> datetime | None:
    """Unix milliseconds → timezone-aware UTC. Zero and negative are empty."""
    try:
        value = int(ms or 0)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)


def require_utc(ts: datetime) -> datetime:
    """Raise if ``ts`` is naive. Return UTC-normalized datetime."""
    if not isinstance(ts, datetime):
        raise TypeError("timestamp must be datetime")
    if ts.tzinfo is None:
        raise ValueError("naive timestamp rejected")
    return ts.astimezone(timezone.utc)


def utc_from_any(raw: Any) -> datetime | None:
    """Parse NT unix-ms, pandas, or ISO. Naive strings are treated as UTC (Z)."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        if raw.tzinfo is None:
            return raw.replace(tzinfo=timezone.utc)
        return raw.astimezone(timezone.utc)
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if raw > 1_000_000_000_000:
            return utc_from_unix_ms(int(raw))
        if raw > 1_000_000_000:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = pd.to_datetime(text, utc=True).to_pydatetime()
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_z(ts: datetime) -> str:
    return require_utc(ts).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
