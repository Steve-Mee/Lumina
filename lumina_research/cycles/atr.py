"""Causal RTH-session ATR in index points. Equal for micro and mini."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from lumina_research.cycles.data import ResearchBar

ATR_N_SESSIONS = 14


def causal_session_atr(
    bars: Sequence[ResearchBar],
    session_dates: Sequence[date],
    rth: Sequence[bool],
    *,
    n_sessions: int = ATR_N_SESSIONS,
) -> tuple[float, ...]:
    """ATR at bar i is the mean RTH true-range of up to ``n_sessions`` prior sessions.

    True range of a session = RTH high − RTH low. The current session is excluded.
    """
    if n_sessions < 1:
        raise ValueError("n_sessions must be >= 1")
    if len(bars) != len(session_dates) or len(bars) != len(rth):
        raise ValueError("ATR series must align")
    ranges: dict[date, tuple[float, float]] = {}
    order: list[date] = []
    for bar, session, is_rth in zip(bars, session_dates, rth, strict=True):
        if not is_rth:
            continue
        if session not in ranges:
            ranges[session] = (bar.high, bar.low)
            order.append(session)
        else:
            hi, lo = ranges[session]
            ranges[session] = (max(hi, bar.high), min(lo, bar.low))
    completed = [ranges[day][0] - ranges[day][1] for day in order]
    session_atr: dict[date, float] = {}
    for index, day in enumerate(order):
        prior = completed[max(0, index - n_sessions) : index]
        session_atr[day] = (sum(prior) / float(len(prior))) if prior else 0.0
    out = [session_atr.get(session, 0.0) for session in session_dates]
    return tuple(out)


def points_to_ticks(points: float, *, tick_size: float) -> int:
    if tick_size <= 0.0:
        raise ValueError("tick_size must be positive")
    ticks = int(round(float(points) / tick_size))
    return max(1, ticks)
