"""Venue proof floors — fail-closed when data is thin (Wave 3)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.challenger_venue.journal import load_journal

DEFAULT_MIN_DAYS = 5
DEFAULT_MIN_TRADES = 50


def _parse_ts(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def venue_proof(
    workspace: Path | str,
    *,
    min_days: int = DEFAULT_MIN_DAYS,
    min_trades: int = DEFAULT_MIN_TRADES,
    gap_passed: bool,
) -> dict[str, Any]:
    rows = [r for r in load_journal(workspace) if str(r.get("reason") or "") == "fill"]
    if len(rows) < int(min_trades):
        return {
            "ready": False,
            "notify_allowed": False,
            "reason": "thin_trades",
            "trades": len(rows),
            "days": 0,
        }
    stamps = [_parse_ts(r.get("ts") or r.get("timestamp")) for r in rows]
    known = [s for s in stamps if s is not None]
    days = 0
    if len(known) >= 2:
        days = max(0, (max(known) - min(known)).days)
    elif known:
        days = 0
    if days < int(min_days):
        return {
            "ready": False,
            "notify_allowed": False,
            "reason": "thin_days",
            "trades": len(rows),
            "days": days,
        }
    if not gap_passed:
        return {
            "ready": False,
            "notify_allowed": False,
            "reason": "reality_gap",
            "trades": len(rows),
            "days": days,
        }
    return {
        "ready": True,
        "notify_allowed": True,
        "reason": "ok",
        "trades": len(rows),
        "days": days,
    }
