"""Window and clock of one frozen sentence. No named market pattern.

A bar is 1 to 1440 real minutes. A missing open minute is a hole and the
signal is false. A scheduled Globex close is not a hole.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from lumina_core.market.globex_hours import globex_status
from lumina_core.market.minute_bars import MinuteBar

MINUTE_NS = 60 * 1_000_000_000
BAR_MINUTES_MAX = 1440
ET = ZoneInfo("America/New_York")
_REAL_NS = 10**17


def bar_minutes_of(sentence: dict[str, Any]) -> int:
    try:
        size = int(sentence.get("bar_minutes") or 1)
    except (TypeError, ValueError):
        return 0
    if size < 1 or size > BAR_MINUTES_MAX:
        return 0
    return size


def clock_open(ts_ns: int, clock: dict[str, Any] | None) -> bool:
    if not isinstance(clock, dict):
        return True
    if int(ts_ns) < _REAL_NS:
        return True
    instant = datetime.fromtimestamp(int(ts_ns) / 1_000_000_000, tz=timezone.utc).astimezone(ET)
    weekdays = clock.get("weekdays")
    if isinstance(weekdays, list) and weekdays and instant.weekday() not in {int(item) for item in weekdays}:
        return False
    months = clock.get("months")
    if isinstance(months, list) and months and instant.month not in {int(item) for item in months}:
        return False
    if "start_min" not in clock and "end_min" not in clock:
        return True
    try:
        start = int(clock["start_min"])
        end = int(clock["end_min"])
    except (KeyError, TypeError, ValueError):
        return False
    minute = instant.hour * 60 + instant.minute
    return start <= minute < end


def scheduled_gap(start_ns: int, end_ns: int) -> bool:
    """True when every minute strictly between the two stamps is closed."""
    if int(end_ns) - int(start_ns) <= MINUTE_NS:
        return False
    if int(start_ns) < _REAL_NS:
        return False
    cursor = int(start_ns) + MINUTE_NS
    # MINUTE_NS is one minute. Eight days covers a holiday weekend without a long walk.
    limit = int(start_ns) + 8 * 24 * 60 * MINUTE_NS
    while cursor < int(end_ns):
        moment = datetime.fromtimestamp(cursor / 1_000_000_000, tz=timezone.utc)
        try:
            status = globex_status(moment)
        except ValueError:
            return False
        if status == "open":
            return False
        cursor += MINUTE_NS
        if cursor > limit:
            return False
    return True


def has_open_hole(bars: tuple[MinuteBar, ...]) -> bool:
    for earlier, later in zip(bars, bars[1:], strict=False):
        gap = int(later.ts_ns) - int(earlier.ts_ns)
        if gap == MINUTE_NS:
            continue
        if gap <= 0:
            return True
        if not scheduled_gap(int(earlier.ts_ns), int(later.ts_ns)):
            return True
    return False


def _merge(chunk: tuple[MinuteBar, ...]) -> MinuteBar:
    return MinuteBar(
        ts_ns=chunk[-1].ts_ns,
        open_ticks=chunk[0].open_ticks,
        high_ticks=max(bar.high_ticks for bar in chunk),
        low_ticks=min(bar.low_ticks for bar in chunk),
        close_ticks=chunk[-1].close_ticks,
        volume=sum(bar.volume for bar in chunk),
    )


def composed_tail(minutes: tuple[MinuteBar, ...], sentence: dict[str, Any]) -> tuple[MinuteBar, ...] | None:
    """The bars the sentence may read. None when the window has a hole or is too short."""
    size = bar_minutes_of(sentence)
    if size == 0 or not minutes:
        return None
    unit = str(sentence.get("window_unit") or "bars")
    if unit == "calendar":
        return _calendar_slice(minutes, str(sentence.get("calendar") or ""))
    try:
        count = int(sentence.get("window") or 0)
    except (TypeError, ValueError):
        return None
    if count < 1:
        return None
    need = size * count
    if len(minutes) < need:
        return None
    tail = minutes[-need:]
    if has_open_hole(tail):
        return None
    return tuple(_merge(tail[offset : offset + size]) for offset in range(0, need, size))


def _calendar_slice(minutes: tuple[MinuteBar, ...], kind: str) -> tuple[MinuteBar, ...] | None:
    end = datetime.fromtimestamp(minutes[-1].ts_ns / 1_000_000_000, tz=timezone.utc)
    if kind == "day":
        start = end.replace(hour=0, minute=0, second=0, microsecond=0)
    elif kind == "week":
        start = (end - timedelta(days=end.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif kind == "month":
        start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif kind == "quarter":
        month = ((end.month - 1) // 3) * 3 + 1
        start = end.replace(month=month, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        return None
    start_ns = int(start.timestamp() * 1_000_000_000)
    chosen = tuple(bar for bar in minutes if bar.ts_ns >= start_ns)
    if len(chosen) < 2 or has_open_hole(chosen):
        return None
    if chosen[0].ts_ns - start_ns > MINUTE_NS and not scheduled_gap(start_ns, chosen[0].ts_ns):
        return None
    return chosen


def tail_can_grade(sentence: dict[str, Any], bars: tuple[MinuteBar, ...]) -> bool:
    """The locked slice can host one episode of this sentence. Prices are not read."""
    if len(bars) < 2:
        return False
    unit = str(sentence.get("window_unit") or "bars")
    if unit == "bars":
        try:
            need = int(sentence.get("bar_minutes") or 1) * int(sentence.get("window") or 1)
        except (TypeError, ValueError):
            return False
        if need < 1 or len(bars) <= need + 1:
            return False
    elif unit == "calendar":
        if _calendar_slice(bars, str(sentence.get("calendar") or "")) is None:
            return False
    else:
        return False
    clock = sentence.get("clock")
    if not isinstance(clock, dict):
        return True
    months = clock.get("months")
    if isinstance(months, list) and months:
        found = {_part(bar.ts_ns, "month") for bar in bars}
        found.discard(None)
        if found.isdisjoint({int(item) for item in months}):
            return False
    weekdays = clock.get("weekdays")
    if isinstance(weekdays, list) and weekdays:
        found_days = {_part(bar.ts_ns, "weekday") for bar in bars}
        found_days.discard(None)
        if found_days.isdisjoint({int(item) for item in weekdays}):
            return False
    return True


def _part(ts_ns: int, kind: str) -> int | None:
    if int(ts_ns) < _REAL_NS:
        return None
    instant = datetime.fromtimestamp(int(ts_ns) / 1_000_000_000, tz=timezone.utc).astimezone(ET)
    if kind == "month":
        return int(instant.month)
    return int(instant.weekday())


def signal_on(sentence: dict[str, Any], history: tuple[MinuteBar, ...], *, tick_size: float) -> bool:
    if "compare" not in sentence:
        return False
    if not clock_open(history[-1].ts_ns if history else 0, sentence.get("clock") if isinstance(sentence.get("clock"), dict) else None):
        return False
    used = composed_tail(history, sentence)
    if not used:
        return False
    closes = [bar.close_ticks * tick_size for bar in used]
    kind = str(sentence.get("compare") or "")
    if kind == "range_pos":
        low = min(bar.low_ticks for bar in used) * tick_size
        high = max(bar.high_ticks for bar in used) * tick_size
        if high <= low or closes[-1] <= 0.0:
            return False
        pos = (closes[-1] - low) / (high - low)
        if sentence.get("quarter") == "top":
            return pos >= 0.75
        return pos <= 0.25
    if kind == "return":
        if closes[0] <= 0.0:
            return False
        change = (closes[-1] - closes[0]) / closes[0]
        return change > 0.0 if int(sentence.get("side") or 0) > 0 else change < 0.0
    if kind == "volatility":
        if closes[-1] <= 0.0:
            return False
        span = max(closes) - min(closes)
        return span / closes[-1] >= float(sentence.get("vol_min") or 0.0)
    return False
