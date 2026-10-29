"""Drop known gaps (never fill), mark roll and hole breaks, label high-vol sessions."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import date
from typing import Sequence

from lumina_research.cycles.data import ResearchBar
from lumina_research.cycles.gaps import in_known_gap, interval_crosses_gap
from lumina_research.cycles.rolls import is_roll_session
from lumina_research.cycles.sessions import INTRASESSION_HOLE_NS, SessionLabels, annotate
from lumina_research.monitoring.acceptance import (
    HIGH_VOL_REALIZED_WINDOW,
    HIGH_VOL_TRAILING_PCT,
    HIGH_VOL_TRAILING_WINDOW,
)


@dataclass(frozen=True, slots=True)
class PreparedTape:
    instrument: str
    bars: tuple[ResearchBar, ...]
    session_dates: tuple[date, ...]
    rth: tuple[bool, ...]
    breaks: tuple[bool, ...]
    quiet: tuple[bool, ...]
    dropped: int
    n_breaks: int


def prepare_tape(instrument: str, bars: Sequence[ResearchBar]) -> PreparedTape:
    kept = tuple(item for item in bars if not in_known_gap(instrument, item.ts_ns))
    dropped = len(bars) - len(kept)
    labels = annotate(kept)
    breaks = _breaks(instrument, kept, labels)
    quiet = _quiet_mask(kept, labels.session_dates)
    return PreparedTape(
        instrument=instrument,
        bars=kept,
        session_dates=labels.session_dates,
        rth=labels.rth,
        breaks=breaks,
        quiet=quiet,
        dropped=dropped,
        n_breaks=sum(1 for item in breaks if item),
    )


def _breaks(instrument: str, bars: Sequence[ResearchBar], labels: SessionLabels) -> tuple[bool, ...]:
    out: list[bool] = []
    first_of_session: set[date] = set()
    previous_ts = 0
    previous_session: date | None = None
    for index, bar in enumerate(bars):
        session = labels.session_dates[index]
        roll = is_roll_session(session) and session not in first_of_session
        first_of_session.add(session)
        hole = False
        crossed = False
        if index > 0 and previous_session is not None:
            delta = int(bar.ts_ns) - previous_ts
            if session == previous_session and delta > INTRASESSION_HOLE_NS:
                hole = True
            crossed = interval_crosses_gap(instrument, previous_ts, int(bar.ts_ns))
        out.append(bool(roll or hole or crossed))
        previous_ts = int(bar.ts_ns)
        previous_session = session
    return tuple(out)


def _quiet_mask(bars: Sequence[ResearchBar], sessions: Sequence[date]) -> tuple[bool, ...]:
    closes: dict[date, float] = {}
    for bar, session in zip(bars, sessions, strict=True):
        closes[session] = bar.close
    high_vol = _high_vol_sessions(closes)
    return tuple(not high_vol.get(session, False) for session in sessions)


def _high_vol_sessions(closes: dict[date, float]) -> dict[date, bool]:
    """20d realized vol > 75th pct of trailing 252d, causal (no same-session look-ahead)."""
    dates = tuple(sorted(closes))
    rets: list[float] = []
    for index, day in enumerate(dates):
        if index == 0:
            rets.append(0.0)
            continue
        prev = closes[dates[index - 1]]
        rets.append(0.0 if prev == 0.0 else (closes[day] - prev) / prev)
    window = HIGH_VOL_REALIZED_WINDOW
    trail = HIGH_VOL_TRAILING_WINDOW
    labels: dict[date, bool] = {}
    realized: list[float] = []
    for index, day in enumerate(dates):
        if index < window:
            labels[day] = False
            continue
        chunk = rets[index - window : index]
        current = float(statistics.pstdev(chunk)) if len(chunk) >= 2 else 0.0
        realized.append(current)
        history = realized[max(0, len(realized) - trail) : -1]
        if len(history) < 8:
            labels[day] = False
            continue
        ordered = sorted(history)
        cap_index = min(len(ordered) - 1, max(0, int(HIGH_VOL_TRAILING_PCT * (len(ordered) - 1))))
        labels[day] = current > ordered[cap_index]
    return labels
