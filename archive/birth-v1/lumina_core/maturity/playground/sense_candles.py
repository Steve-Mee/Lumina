"""Closed higher-timeframe candles from a 1-minute close stream.

A bucket is closed only when a later bar belongs to a later bucket.
The forming candle is never returned. Clock is America/Chicago.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EXCHANGE_TZ = ZoneInfo("America/Chicago")
SPANS_MIN = (5, 60, 240)


def parse_utc(ts: str) -> datetime | None:
    text = str(ts or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def exchange_session_key(ts: str) -> str | None:
    """Chicago calendar date. The journal flushes on this key, not on bar_index."""
    parsed = parse_utc(ts)
    if parsed is None:
        return None
    return parsed.astimezone(EXCHANGE_TZ).date().isoformat()


def _bucket_id(parsed_utc: datetime, span_min: int) -> int:
    local = parsed_utc.astimezone(EXCHANGE_TZ).replace(second=0, microsecond=0)
    minutes = local.hour * 60 + local.minute
    floored = minutes - (minutes % int(span_min))
    start = local.replace(hour=floored // 60, minute=floored % 60)
    return int(start.timestamp())


def closed_candles(
    bars: list[dict[str, float | str]],
    *,
    span_min: int,
) -> list[dict[str, float | int]]:
    """One candle per finished bucket. The bucket that contains the last bar is open."""
    grouped: dict[int, float] = {}
    order: list[int] = []
    last_bucket: int | None = None
    for bar in bars:
        parsed = parse_utc(str(bar.get("ts") or ""))
        try:
            close = float(bar.get("px") or 0.0)
        except (TypeError, ValueError):
            continue
        if parsed is None or close <= 0.0:
            continue
        bucket = _bucket_id(parsed, int(span_min))
        if bucket not in grouped:
            order.append(bucket)
        grouped[bucket] = close
        last_bucket = bucket
    if last_bucket is None:
        return []
    closed = [bucket for bucket in order if bucket != last_bucket]
    return [{"bucket": bucket, "close": float(grouped[bucket])} for bucket in closed]


def open_bucket_end(ts: str, *, span_min: int) -> datetime | None:
    """UTC instant when the candle that contains this bar becomes closed."""
    parsed = parse_utc(ts)
    if parsed is None:
        return None
    start = _bucket_id(parsed, int(span_min))
    return datetime.fromtimestamp(start, tz=timezone.utc) + timedelta(minutes=int(span_min))


def slope_from_closes(closes: list[float]) -> int | None:
    """Sign of the last two native NT closes. Short history is unknown."""
    if len(closes) < 2:
        return None
    previous = float(closes[-2])
    last = float(closes[-1])
    if previous <= 0.0 or last <= 0.0:
        return None
    delta = last - previous
    if abs(delta) <= 1e-9:
        return None
    return 1 if delta > 0.0 else -1


def slope_sign(bars: list[dict[str, float | str]], *, span_min: int) -> int | None:
    """Sign of the last two closed candles. Zero change and a short history are unknown."""
    candles = closed_candles(bars, span_min=span_min)
    if len(candles) < 2:
        return None
    previous = float(candles[-2]["close"])
    last = float(candles[-1]["close"])
    if previous <= 0.0:
        return None
    delta = last - previous
    if abs(delta) <= 1e-9:
        return None
    return 1 if delta > 0.0 else -1
