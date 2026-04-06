from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class SessionGuard:
    """Calendar-aware CME futures session guard for MES/NQ style products."""

    calendar_name: str = "CME"
    exchange_tz: str = "America/Chicago"
    rollover_start_local: time = time(16, 55)
    rollover_end_local: time = time(18, 5)
    _calendar: object | None = field(default=None, init=False, repr=False)
    _tz: ZoneInfo | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            # v51 requirement: use get_calendar("CME") for futures sessions.
            self._calendar = mcal.get_calendar(self.calendar_name)
        except Exception:
            fallback_names = ["CMES", "CME_Equity", "us_futures"]
            calendar = None
            for name in fallback_names:
                try:
                    calendar = mcal.get_calendar(name)
                    logger.info("SessionGuard fallback calendar selected: %s", name)
                    break
                except Exception:
                    continue
            if calendar is None:
                raise
            self._calendar = calendar
        self._tz = ZoneInfo(self.exchange_tz)

    @staticmethod
    def _as_utc(ts: datetime | None) -> datetime:
        candidate = ts or _utcnow()
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=timezone.utc)
        return candidate.astimezone(timezone.utc)

    def _schedule(self, ts: datetime, days_before: int = 1, days_after: int = 7) -> pd.DataFrame:
        start = (ts - timedelta(days=days_before)).date()
        end = (ts + timedelta(days=days_after)).date()
        return self._calendar.schedule(start_date=start, end_date=end)

    def is_market_open(self, ts: datetime | None = None) -> bool:
        """True when CME calendar says instrument is in an open session."""
        now_utc = self._as_utc(ts)
        try:
            schedule = self._schedule(now_utc, days_before=1, days_after=1)
            if schedule.empty:
                return False
            ts_pd = pd.Timestamp(now_utc)
            opens = schedule["market_open"]
            closes = schedule["market_close"]
            return bool(((opens <= ts_pd) & (ts_pd < closes)).any())
        except Exception as exc:
            logger.warning("SessionGuard is_market_open fallback false: %s", exc)
            return False

    def is_rollover_window(self, ts: datetime | None = None) -> bool:
        """True during the daily rollover/maintenance window (fail-closed)."""
        now_local = self._as_utc(ts).astimezone(self._tz).timetz().replace(tzinfo=None)
        return self.rollover_start_local <= now_local <= self.rollover_end_local

    def is_trading_session(self, ts: datetime | None = None) -> bool:
        """True when market is open and not in rollover window."""
        now_utc = self._as_utc(ts)
        return self.is_market_open(now_utc) and not self.is_rollover_window(now_utc)

    def next_open(self, ts: datetime | None = None) -> datetime | None:
        """Return next CME market open timestamp in UTC."""
        now_utc = self._as_utc(ts)
        try:
            schedule = self._schedule(now_utc, days_before=0, days_after=10)
            if schedule.empty:
                return None
            for open_ts in schedule["market_open"].tolist():
                dt = pd.Timestamp(open_ts).to_pydatetime().astimezone(timezone.utc)
                if dt > now_utc:
                    return dt
            return None
        except Exception as exc:
            logger.error("SessionGuard next_open failed: %s", exc)
            return None

    def next_close(self, ts: datetime | None = None) -> datetime | None:
        """Return current-session close or next close timestamp in UTC."""
        now_utc = self._as_utc(ts)
        try:
            schedule = self._schedule(now_utc, days_before=1, days_after=10)
            if schedule.empty:
                return None
            for _, row in schedule.iterrows():
                open_ts = pd.Timestamp(row["market_open"]).to_pydatetime().astimezone(timezone.utc)
                close_ts = pd.Timestamp(row["market_close"]).to_pydatetime().astimezone(timezone.utc)
                if open_ts <= now_utc < close_ts:
                    return close_ts
                if close_ts > now_utc:
                    return close_ts
            return None
        except Exception as exc:
            logger.error("SessionGuard next_close failed: %s", exc)
            return None