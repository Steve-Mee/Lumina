"""Globex session and RTH labels for 1-minute research bars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence

from lumina_core.market.globex_hours import ET, globex_session_date
from lumina_research.cycles.data import ResearchBar

RTH_OPEN_MIN = 9 * 60 + 30
RTH_CLOSE_MIN = 16 * 60
INTRASESSION_HOLE_NS = 90 * 1_000_000_000


@dataclass(frozen=True, slots=True)
class SessionLabels:
    session_dates: tuple[date, ...]
    rth: tuple[bool, ...]


def annotate(bars: Sequence[ResearchBar]) -> SessionLabels:
    dates: list[date] = []
    rth: list[bool] = []
    for bar in bars:
        moment = datetime.fromtimestamp(bar.ts_ns / 1_000_000_000, tz=timezone.utc)
        dates.append(globex_session_date(moment))
        local = moment.astimezone(ET)
        minutes = local.hour * 60 + local.minute
        rth.append(RTH_OPEN_MIN <= minutes < RTH_CLOSE_MIN)
    return SessionLabels(session_dates=tuple(dates), rth=tuple(rth))


def utc_from_ns(ts_ns: int) -> datetime:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc)
