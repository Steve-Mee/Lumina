"""Aggregate 1-minute net returns to Globex session days for the Validation Gate."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from lumina_research.validation.cost_model import MarketSnapshot

Tape = tuple[tuple[float, ...], tuple[float, ...], tuple[MarketSnapshot, ...]]


def daily_net_tape(
    net_1m: Sequence[float],
    session_dates: Sequence[date],
) -> Tape:
    if len(net_1m) != len(session_dates):
        raise ValueError("net returns and session dates must align")
    if not net_1m:
        raise ValueError("empty 1-minute series")
    buckets: dict[date, float] = {}
    order: list[date] = []
    for value, session in zip(net_1m, session_dates, strict=True):
        if session not in buckets:
            buckets[session] = 0.0
            order.append(session)
        buckets[session] += float(value)
    daily = tuple(buckets[day] for day in order)
    n = len(daily)
    positions = tuple(0.0 for _ in range(n))
    markets = tuple(MarketSnapshot(volume=1.0, average_volume=1.0, volatility_price=2.0) for _ in range(n))
    return daily, positions, markets


def unique_sessions(session_dates: Sequence[date]) -> tuple[date, ...]:
    seen: list[date] = []
    found: set[date] = set()
    for item in session_dates:
        if item in found:
            continue
        found.add(item)
        seen.append(item)
    return tuple(seen)
