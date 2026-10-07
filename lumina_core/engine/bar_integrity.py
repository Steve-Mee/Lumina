"""NT is the SSOT for whether a 1-minute bar should exist (ADR-0054).

A missed REAL bar desynchronises ATR, regime, fibs, Playground and stops.
This module never invents OHLC. Completeness is: Lumina's closed 1m set equals
NinjaTrader's closed 1m set for the requested window. Wall-clock holes that NT
also does not have are session (ETH halt, weekend). Holes NT has and we do not
are missed bars — fill from NT, then lock new entries if still incomplete.

OBSERVATION_DIM stays 43. Completeness is blackboard + state JSON, not a new
observation slot.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.nt_bar_ssot import BarRejected, is_forming_bar, validate_nt_bar
from lumina_core.engine.ohlc_clock import iso_z, utc_from_any

# 1m close timestamps are end-of-bar. 120s matches the Playground live window.
FRESH_BAR_MAX_AGE_SEC = 120.0
# Tape quotes older than this do not count as "market is printing".
TAPE_LIVE_MAX_AGE_SEC = 30.0


@dataclass(frozen=True, slots=True)
class BarBookStatus:
    complete: bool
    reason: str
    missing_count: int
    filled_count: int
    session_holes: int
    lock_new_entries: bool
    last_closed: datetime | None
    message: str

    def as_payload(self) -> dict[str, Any]:
        last = iso_z(self.last_closed) if self.last_closed is not None else ""
        return {
            "complete": bool(self.complete),
            "reason": str(self.reason),
            "missing_count": int(self.missing_count),
            "filled_count": int(self.filled_count),
            "session_holes": int(self.session_holes),
            "lock_new_entries": bool(self.lock_new_entries),
            "last_closed": last,
            "message": str(self.message),
            "period": "1m",
        }


def _ts_key(ts: datetime) -> int:
    return int(ts.astimezone(timezone.utc).timestamp())


def tape_is_live(quotes: Any, now: datetime, *, max_age_sec: float = TAPE_LIVE_MAX_AGE_SEC) -> bool:
    """True when the last tape print is fresh. A leftover deque after halt is not live."""
    if not quotes:
        return False
    last = quotes[-1]
    if not isinstance(last, dict):
        return False
    ts = utc_from_any(last.get("timestamp") or last.get("timestamp_unix_ms"))
    if ts is None:
        return False
    now_utc = utc_from_any(now) or datetime.now(timezone.utc)
    age = (now_utc - ts).total_seconds()
    return -5.0 <= age <= float(max_age_sec)


def reconcile_against_nt(
    *,
    local_closed: list[datetime],
    nt_rows: list[dict[str, Any]] | None,
    nt_ok: bool,
    now: datetime,
    quotes_live: bool,
    filled_count: int = 0,
) -> tuple[BarBookStatus, list[dict[str, Any]]]:
    """Compare local closed 1m timestamps to NT. Returns status + bars to apply.

    Completeness is set-equality on the overlapping closed window. The forming
    bar (close timestamp still in the future) is not a closed bar and is never
    filled or counted as missing. NT barsBack snapshots are a tail — older
    local bars outside that tail are not extras.
    """
    now_utc = utc_from_any(now) or datetime.now(timezone.utc)
    local_keys = {_ts_key(ts) for ts in local_closed if utc_from_any(ts) is not None}

    if not nt_ok:
        last = max(local_closed) if local_closed else None
        status = BarBookStatus(
            complete=False,
            reason="nt_unreachable",
            missing_count=0,
            filled_count=int(filled_count),
            session_holes=0,
            lock_new_entries=True,
            last_closed=last,
            message="NinjaTrader historical fill failed — new entries locked",
        )
        return status, []

    accepted: list[dict[str, Any]] = []
    nt_keys: set[int] = set()
    nt_last: datetime | None = None
    for raw in nt_rows or []:
        try:
            bar = validate_nt_bar(raw)
        except BarRejected:
            continue
        ts = bar["timestamp"]
        if is_forming_bar(ts, now_utc):
            continue
        key = _ts_key(ts)
        nt_keys.add(key)
        accepted.append(bar)
        if nt_last is None or ts > nt_last:
            nt_last = ts

    if nt_keys:
        window_lo = min(nt_keys)
        window_hi = max(nt_keys)
        local_in_window = {k for k in local_keys if window_lo <= k <= window_hi}
    else:
        local_in_window = set()

    missing_keys = nt_keys - local_in_window
    to_apply = [bar for bar in accepted if _ts_key(bar["timestamp"]) in missing_keys]
    to_apply.sort(key=lambda row: _ts_key(row["timestamp"]))

    last_closed = nt_last
    if last_closed is None and local_closed:
        last_closed = max(local_closed)

    if missing_keys:
        status = BarBookStatus(
            complete=False,
            reason="filling",
            missing_count=len(missing_keys),
            filled_count=int(filled_count),
            session_holes=0,
            lock_new_entries=True,
            last_closed=last_closed,
            message=f"NT has {len(missing_keys)} 1m bar(s) Lumina missed — filling, new entries locked",
        )
        return status, to_apply

    extra = local_in_window - nt_keys
    if extra and nt_keys:
        status = BarBookStatus(
            complete=False,
            reason="unexplained_hole",
            missing_count=0,
            filled_count=int(filled_count),
            session_holes=0,
            lock_new_entries=True,
            last_closed=last_closed,
            message="Lumina has 1m bars NinjaTrader does not — book is not NT-equal",
        )
        return status, []

    age = None
    if last_closed is not None:
        age = (now_utc - last_closed).total_seconds()

    if last_closed is None:
        status = BarBookStatus(
            complete=False,
            reason="empty",
            missing_count=0,
            filled_count=int(filled_count),
            session_holes=0,
            lock_new_entries=True,
            last_closed=None,
            message="No NT 1m bars in the book — new entries locked",
        )
        return status, []

    if age is not None and age <= FRESH_BAR_MAX_AGE_SEC:
        status = BarBookStatus(
            complete=True,
            reason="complete",
            missing_count=0,
            filled_count=int(filled_count),
            session_holes=0,
            lock_new_entries=False,
            last_closed=last_closed,
            message="Closed 1m book matches NinjaTrader",
        )
        return status, []

    if quotes_live:
        status = BarBookStatus(
            complete=False,
            reason="unexplained_hole",
            missing_count=0,
            filled_count=int(filled_count),
            session_holes=0,
            lock_new_entries=True,
            last_closed=last_closed,
            message="Tape is live but NT 1m last close is stale — new entries locked",
        )
        return status, []

    status = BarBookStatus(
        complete=True,
        reason="session_hole",
        missing_count=0,
        filled_count=int(filled_count),
        session_holes=1,
        lock_new_entries=False,
        last_closed=last_closed,
        message="NT has no newer 1m bar and tape is quiet — session/halt, not a missed bar",
    )
    return status, []


def entries_blocked(engine: Any) -> tuple[bool, str]:
    """True when new risk-bearing entries must HOLD. Flatten/reduce-only stay open."""
    mode = str(getattr(getattr(engine, "config", None), "trade_mode", "sim") or "sim").strip().lower()
    md = getattr(engine, "market_data", None)
    if md is None:
        if mode in {"real", "sim_real_guard"}:
            return True, "market data manager missing — new entries locked"
        return False, ""
    status = getattr(md, "integrity", None)
    if isinstance(status, BarBookStatus):
        if status.lock_new_entries:
            return True, status.message
        return False, ""
    ohlc = getattr(md, "ohlc_1min", None)
    empty = ohlc is None or getattr(ohlc, "empty", True)
    if empty and mode in {"real", "sim_real_guard"}:
        return True, "OHLC book empty — NT 1m bars missing"
    return False, ""
