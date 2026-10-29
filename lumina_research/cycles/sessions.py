"""Globex session and RTH labels for 1-minute research bars.

Bar timestamps are UTC **close** times (P2 NT8 export). Cash RTH is 09:30-16:00 ET
of clock time, so the first RTH close is 09:31 ET and the last is 16:00 ET.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Sequence

from lumina_core.market.globex_hours import ET, globex_session_date
from lumina_research.cycles.data import ResearchBar

# Close-time labels: 09:31 ET covers 09:30-09:31; 16:00 ET covers 15:59-16:00.
RTH_OPEN_CLOSE_MIN = 9 * 60 + 31
RTH_LAST_CLOSE_MIN = 16 * 60
INTRASESSION_HOLE_NS = 90 * 1_000_000_000
# Legacy aliases used by prepare.py hole review.
RTH_OPEN_MIN = RTH_OPEN_CLOSE_MIN
RTH_CLOSE_MIN = RTH_LAST_CLOSE_MIN + 1


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
        rth.append(RTH_OPEN_CLOSE_MIN <= minutes <= RTH_LAST_CLOSE_MIN)
    return SessionLabels(session_dates=tuple(dates), rth=tuple(rth))


def utc_from_ns(ts_ns: int) -> datetime:
    return datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc)


def is_rth_close(ts_ns: int) -> bool:
    moment = utc_from_ns(ts_ns).astimezone(ET)
    minutes = moment.hour * 60 + moment.minute
    return RTH_OPEN_CLOSE_MIN <= minutes <= RTH_LAST_CLOSE_MIN
