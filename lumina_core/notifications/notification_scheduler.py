"""Scheduler for waking-hours-only notification delivery.

Notifications are delivered immediately during Brussels waking hours
(08:00-22:00). Outside that window they are deferred to the next 09:00
Brussels time and delivered by a lightweight background worker.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

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
        self._queue: list[tuple[datetime, Callable[[], bool], str]] = []
        self._lock = threading.RLock()
        self._running = True
        self._worker = threading.Thread(target=self._worker_loop, daemon=True, name="NotificationScheduler-worker")
        self._worker.start()

    def stop(self) -> None:
        self._running = False

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
        with self._lock:
            self._queue.append((scheduled_for, callback, description))
            self._queue.sort(key=lambda item: item[0])
        logger.info("Deferred notification '%s' to %s", description, scheduled_for.isoformat())
        return {
            "accepted": True,
            "sent_now": False,
            "scheduled_for": scheduled_for.isoformat(),
            "description": description,
        }

    def run_pending(self, *, now: datetime | None = None) -> int:
        current = now or datetime.now(timezone.utc)
        due: list[tuple[datetime, Callable[[], bool], str]] = []
        with self._lock:
            while self._queue and self._queue[0][0] <= current:
                due.append(self._queue.pop(0))
        for _, callback, description in due:
            try:
                callback()
            except Exception as exc:  # pragma: no cover
                logger.error("Scheduled notification '%s' failed: %s", description, exc)
        return len(due)

    def _worker_loop(self) -> None:
        while self._running:
            self.run_pending()
            threading.Event().wait(1.0)


__all__ = ["NotificationScheduler"]
