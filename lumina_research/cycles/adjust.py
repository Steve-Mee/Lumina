"""Back-adjust OHLC for indicators. PnL stays on the unadjusted series.

At each NT8 roll session the unadjusted tape jumps. Indicators (z-score, range,
VWAP, trend) must not see that jump. Backward Panama: from the last bar backward,
subtract the roll gap from every earlier price so the series is continuous.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.rolls import is_roll_session


def back_adjust(
    bars: Sequence[ResearchBar],
    session_dates: Sequence[date],
) -> tuple[ResearchBar, ...]:
    n = len(bars)
    if n == 0:
        return ()
    if n != len(session_dates):
        raise ValueError("bars and session dates must align for back-adjustment")
    gaps = [0.0] * n
    for index in range(1, n):
        session = session_dates[index]
        if session == session_dates[index - 1]:
            continue
        if not is_roll_session(session):
            continue
        gaps[index] = float(bars[index].open) - float(bars[index - 1].close)
    cumulative = 0.0
    offsets = [0.0] * n
    for index in range(n - 1, -1, -1):
        cumulative += gaps[index]
        offsets[index] = cumulative
    # The first bar of a roll session is the new contract: it must not carry the gap
    # that was just added (that gap belongs to all *earlier* bars).
    out: list[ResearchBar] = []
    for index, bar in enumerate(bars):
        shift = offsets[index] - gaps[index]
        out.append(
            ResearchBar(
                ts_ns=bar.ts_ns,
                open=bar.open + shift,
                high=bar.high + shift,
                low=bar.low + shift,
                close=bar.close + shift,
                volume=bar.volume,
            )
        )
    return tuple(out)
