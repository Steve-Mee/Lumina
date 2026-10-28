"""Session flat. The account does not carry a position through the Globex halt.

``overnight_allowed`` is false unless the seal says true. A missing field is false.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from lumina_core.market.globex_hours import globex_status
from lumina_core.maturity.playground.envelope import read_seal

_REAL_NS = 10**17


def overnight_allowed(workspace_root: Path | str) -> bool:
    raw = read_seal(workspace_root) or {}
    return raw.get("overnight_allowed") is True


def hold_crosses_halt(now_ns: int, hold_minutes: int) -> bool:
    """True when the hold would still be open at or after the next halt."""
    if int(now_ns) < _REAL_NS:
        return False
    start = datetime.fromtimestamp(int(now_ns) / 1_000_000_000, tz=timezone.utc)
    try:
        if globex_status(start) != "open":
            return True
    except ValueError:
        return True
    end = start + timedelta(minutes=max(1, int(hold_minutes)))
    cursor = start
    while cursor <= end:
        try:
            status = globex_status(cursor)
        except ValueError:
            return True
        if status != "open":
            return True
        cursor += timedelta(minutes=1)
    return False


def note_stale_open_feed(workspace_root: Path | str, *, now: datetime | None = None) -> str | None:
    """The open book refuses a missing minute. It does not invent one."""
    from lumina_core.market.minute_bars import load_minutes
    from lumina_core.maturity.playground.progress import load_playground_progress, merge_playground_progress

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        return None
    try:
        if globex_status(moment) != "open":
            return None
    except ValueError:
        return None
    root = Path(workspace_root)
    from lumina_core.maturity.playground.learning_book import read_header

    listing = str(load_playground_progress(root).get("chart_listing") or read_header(root).get("symbol") or "")
    if not listing:
        return None
    try:
        bars = load_minutes(root, listing)
    except (OSError, ValueError):
        bars = ()
    now_ns = int(moment.timestamp() * 1_000_000_000)
    stale = not bars or now_ns - int(bars[-1].ts_ns) > 180 * 1_000_000_000
    if not stale:
        return None
    merge_playground_progress(root, {"feed_refused": "no_fresh_closed_minute"})
    return "feed_refused"
