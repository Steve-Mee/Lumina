from __future__ import annotations

import concurrent.futures
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
import logging
from typing import Protocol
from zoneinfo import ZoneInfo

import pandas as pd
import pandas_market_calendars as mcal

logger = logging.getLogger(__name__)


class _CalendarProtocol(Protocol):
    def schedule(self, *, start_date: date, end_date: date) -> pd.DataFrame: ...


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class SessionGuard:
    """Calendar-aware CME futures session guard for MES/NQ style products."""

    calendar_name: str = "CME"
    exchange_tz: str = "America/Chicago"
    rollover_start_local: time = time(16, 55)
    rollover_end_local: time = time(18, 5)
    schedule_timeout_seconds: float = 2.0
    _calendar: _CalendarProtocol | None = field(default=None, init=False, repr=False)
    _tz: ZoneInfo | None = field(default=None, init=False, repr=False)
    _schedule_executor: concurrent.futures.ThreadPoolExecutor | None = field(default=None, init=False, repr=False)
    _schedule_cache: dict[tuple[date, date], pd.DataFrame] = field(default_factory=dict, init=False, repr=False)

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
        self._schedule_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    @staticmethod
    def _as_utc(ts: datetime | None) -> datetime:
        candidate = ts or _utcnow()
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=timezone.utc)
        return candidate.astimezone(timezone.utc)

    def _schedule(self, ts: datetime, days_before: int = 1, days_after: int = 7) -> pd.DataFrame:
        start = (ts - timedelta(days=days_before)).date()
        end = (ts + timedelta(days=days_after)).date()
        cache_key = (start, end)
        cached = self._schedule_cache.get(cache_key)
        if cached is not None:
            return cached

        calendar = self._calendar
        if calendar is None:
            raise RuntimeError("SessionGuard calendar is not initialized")

        executor = self._schedule_executor
        if executor is None:
            raise RuntimeError("SessionGuard schedule executor is not initialized")

        def _run_schedule() -> pd.DataFrame:
            return calendar.schedule(start_date=start, end_date=end)

        future = executor.submit(_run_schedule)
        try:
            schedule = future.result(timeout=max(0.1, float(self.schedule_timeout_seconds)))
        except BaseException as exc:
            future.cancel()
            raise RuntimeError(f"SessionGuard schedule call failed: {exc}") from exc

        if len(self._schedule_cache) > 32:
            self._schedule_cache.clear()
        self._schedule_cache[cache_key] = schedule
        return schedule

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

    def should_force_close_eod(self, ts: datetime | None = None, force_close_minutes: int = 30) -> bool:
        """
        Check if we're within the force-close window (N minutes before session end).
        Capital preservation: close all positions to avoid overnight gap risk.
        """
        now_utc = self._as_utc(ts)
        session_close = self.next_close(now_utc)
        if session_close is None:
            return False

        close_window_start = session_close - timedelta(minutes=force_close_minutes)
        return close_window_start <= now_utc < session_close

    def should_block_new_eod_trades(self, ts: datetime | None = None, no_new_trades_minutes: int = 60) -> bool:
        """
        Check if we're within the no-new-trades window (N minutes before session end).
        Capital preservation: don't open new positions near session end.
        """
        now_utc = self._as_utc(ts)
        session_close = self.next_close(now_utc)
        if session_close is None:
            return False

        no_new_trades_start = session_close - timedelta(minutes=no_new_trades_minutes)
        return no_new_trades_start <= now_utc < session_close

    def is_overnight_gap_risk(self, ts: datetime | None = None) -> bool:
        """
        Check if we're exposed to overnight gap risk (after session close, before next open).
        Returns True if time is between current session close and next session open.
        """
        now_utc = self._as_utc(ts)
        session_close = self.next_close(now_utc)
        session_open = self.next_open(now_utc)

        if session_close is None or session_open is None:
            return False

        # If session_open is next day AND we're open to current close, we're at EOD
        # and overnight gap is upcoming
        return now_utc >= session_close and now_utc < session_open

    def minutes_to_session_end(self, ts: datetime | None = None) -> float:
        """Return minutes until current trading session ends. Negative if session closed."""
        now_utc = self._as_utc(ts)
        session_close = self.next_close(now_utc)
        if session_close is None:
            return -1.0
        minutes = (session_close - now_utc).total_seconds() / 60.0
        return minutes
