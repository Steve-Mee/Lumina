"""Scheduler for waking-hours-only notification delivery.

Notifications are delivered immediately during Brussels waking hours
(08:00-22:00). Outside that window they are deferred to the next 09:00
Brussels time and delivered by APScheduler.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

logger = logging.getLogger(__name__)


class NotificationScheduler:
    def __init__(
        self,
        *,
        timezone_name: str = "Europe/Brussels",
        waking_hour_start: int = 8,
        waking_hour_end: int = 22,
        default_hour: int = 9,
    ) -> None:
        self._tz = ZoneInfo(timezone_name)
        self._waking_hour_start = int(waking_hour_start)
        self._waking_hour_end = int(waking_hour_end)
        self._default_hour = int(default_hour)
        self._scheduler = BackgroundScheduler(timezone=self._tz)
        self._scheduler.start()

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def is_in_waking_hours(self, dt: datetime) -> bool:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone(self._tz)
        return self._waking_hour_start <= local_dt.hour < self._waking_hour_end

    def next_delivery_time(self, from_dt: datetime | None = None) -> datetime:
        source = from_dt or datetime.now(timezone.utc)
        if source.tzinfo is None:
            source = source.replace(tzinfo=timezone.utc)
        local_dt = source.astimezone(self._tz)
        if self.is_in_waking_hours(source):
            return source
        candidate = local_dt.replace(hour=self._default_hour, minute=0, second=0, microsecond=0)
        if local_dt >= candidate:
            candidate = candidate + timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    def schedule_notification(
        self,
        *,
        callback: Callable[[], bool],
        description: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        if self.is_in_waking_hours(current):
            sent = bool(callback())
            return {
                "accepted": True,
                "sent_now": sent,
                "scheduled_for": current.isoformat(),
                "description": description,
            }

        scheduled_for = self.next_delivery_time(current)
        try:
            self._scheduler.add_job(
                callback,
                trigger=DateTrigger(run_date=scheduled_for),
                id=f"notif:{description}:{scheduled_for.timestamp()}",
                replace_existing=False,
                coalesce=True,
                misfire_grace_time=120,
                max_instances=1,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to schedule notification '%s': %s", description, exc)
            return {
                "accepted": False,
                "sent_now": False,
                "scheduled_for": scheduled_for.isoformat(),
                "description": description,
            }
        logger.info("Deferred notification '%s' to %s", description, scheduled_for.isoformat())
        return {
            "accepted": True,
            "sent_now": False,
            "scheduled_for": scheduled_for.isoformat(),
            "description": description,
        }

    def run_pending(self, *, now: datetime | None = None) -> int:
        del now
        jobs = self._scheduler.get_jobs()
        return len(jobs)


__all__ = ["NotificationScheduler"]
