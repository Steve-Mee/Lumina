"""Time-boxed allowlist exemptions — never unload mid-trade (K16)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class AllowlistExemption:
    target: str
    expires_at: datetime
    reason: str


def on_exemption_expiry(
    exemption: AllowlistExemption,
    *,
    now: datetime | None = None,
    open_challenger_position: bool,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if exemption.expires_at.tzinfo is None:
        expires = exemption.expires_at.replace(tzinfo=timezone.utc)
    else:
        expires = exemption.expires_at
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if current < expires:
        return {"expired": False, "stop_new_applies": False, "unload": False}
    if open_challenger_position:
        return {
            "expired": True,
            "stop_new_applies": True,
            "unload": False,
            "reason": "open_position_hold",
        }
    return {
        "expired": True,
        "stop_new_applies": True,
        "unload": True,
        "reason": "expired_flat",
    }
