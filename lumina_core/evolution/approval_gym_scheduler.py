"""Scheduler for periodic DNA approval gymnasium sessions with Telegram integration."""
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from lumina_core.state.state_manager import safe_append_jsonl

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore[no-redef]

_BRUSSELS_TZ = ZoneInfo("Europe/Brussels")
_WAKING_HOUR_START = 8
_WAKING_HOUR_END = 22
_DEFAULT_MORNING_HOUR = 9

logger = logging.getLogger(__name__)


class ApprovalGymScheduler:
    """Manages periodic DNA approval gym sessions with optional Telegram notifications.

    Sessions are only scheduled within Brussels waking hours (08:00-22:00).
    Outside waking hours, the next session is deferred to 09:00 Brussels time.
    """

    _instance: Optional["ApprovalGymScheduler"] = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs) -> "ApprovalGymScheduler":
        with cls._lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._initialized = False  # type: ignore[attr-defined]
                cls._instance = obj
        return cls._instance

    def __init__(
        self,
        approval_gym: Optional[Any] = None,
        telegram_notifier: Optional[Any] = None,
        interval_hours: int = 6,
        history_path: str = "state/gym_session_history.jsonl",
        notification_scheduler: Optional[Any] = None,
    ):
        if getattr(self, "_initialized", False):
            return
        self._approval_gym = approval_gym
        self._telegram_notifier = telegram_notifier
        self._notification_scheduler = notification_scheduler
        self._interval_hours = max(1, int(interval_hours))
        self._history_path = Path(history_path)
        self._history_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_session_time: Optional[datetime] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._initialized = True

    def start_scheduler(self) -> bool:
        with self._lock:
            if self._running:
                logger.warning("Scheduler already running.")
                return False
            if self._approval_gym is None:
                logger.error("No ApprovalGym configured. Scheduler cannot start.")
                return False
            self._running = True
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True,
                name="ApprovalGymScheduler-worker",
            )
            self._scheduler_thread.start()
            logger.info(f"Approval Gym scheduler started (interval: {self._interval_hours}h)")
            return True

    def stop_scheduler(self) -> bool:
        with self._lock:
            if not self._running:
                logger.warning("Scheduler not running.")
                return False
            self._running = False
            logger.info("Approval Gym scheduler stopped.")
            return True

    def _scheduler_loop(self) -> None:
        """Background loop: run gym sessions at configured intervals within Brussels waking hours."""
        logger.info(f"Scheduler loop started (interval: {self._interval_hours}h)")

        while self._running:
            try:
                now = datetime.now(timezone.utc)
                if self._last_session_time is None:
                    next_session = self._next_waking_session_time(now)
                else:
                    next_session = self._last_session_time + timedelta(hours=self._interval_hours)
                    if not self._is_in_waking_hours(next_session):
                        next_session = self._next_waking_session_time(next_session)
                        logger.info(f"Next gym session pushed to Brussels waking hours: {next_session.isoformat()}")

                wait_seconds = max(0, (next_session - now).total_seconds())
                if wait_seconds > 0:
                    logger.debug(f"Next gym session in {wait_seconds:.0f}s (Brussels waking hours)")
                    remaining = wait_seconds
                    while remaining > 0 and self._running:
                        threading.Event().wait(min(1.0, remaining))
                        remaining -= 1.0

                if self._running:
                    if not self._is_in_waking_hours(datetime.now(timezone.utc)):
                        logger.info("Outside Brussels waking hours at session start – rescheduling.")
                        self._last_session_time = None
                        continue
                    self._run_scheduled_session()

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
                if self._running:
                    threading.Event().wait(5.0)

    # ------------------------------------------------------------------
    # Brussels waking hours helpers
    # ------------------------------------------------------------------

    def _is_in_waking_hours(self, dt: datetime) -> bool:
        """Return True if dt falls within Brussels waking hours (08:00-22:00)."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        brussels_hour = dt.astimezone(_BRUSSELS_TZ).hour
        return _WAKING_HOUR_START <= brussels_hour < _WAKING_HOUR_END

    def _next_waking_session_time(self, from_dt: datetime) -> datetime:
        """Return next 09:00 Brussels time on or after from_dt."""
        if from_dt.tzinfo is None:
            from_dt = from_dt.replace(tzinfo=timezone.utc)
        brussels_now = from_dt.astimezone(_BRUSSELS_TZ)
        candidate = brussels_now.replace(hour=_DEFAULT_MORNING_HOUR, minute=0, second=0, microsecond=0)
        if brussels_now >= candidate:
            candidate = candidate + timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    # ------------------------------------------------------------------
    # Brussels-aware Telegram helper
    # ------------------------------------------------------------------

    def _notify(self, message: str, description: str) -> None:
        """Send Telegram message, respecting Brussels waking hours via NotificationScheduler."""
        if not self._telegram_notifier:
            return
        notifier = self._telegram_notifier
        if self._notification_scheduler is not None:
            try:
                self._notification_scheduler.schedule_notification(
                    callback=lambda: notifier._send_telegram_message(message),
                    description=description,
                )
                return
            except Exception as exc:
                logger.warning("Failed to schedule notification '%s': %s", description, exc)
        # Fallback: direct send (no Brussels guard)
        try:
            notifier._send_telegram_message(message)
        except Exception as exc:
            logger.warning("Direct Telegram send failed for '%s': %s", description, exc)

    # ------------------------------------------------------------------
    # Session execution
    # ------------------------------------------------------------------

    def _run_scheduled_session(self) -> None:
        """Execute a single scheduled approval gym session."""
        session_time = datetime.now(timezone.utc)
        session_id = session_time.isoformat()

        try:
            if self._telegram_notifier:
                try:
                    msg = (
                        f"Approval Gym Session Starting\n"
                        f"Session ID: {session_id}\n"
                        f"Steve, prepare for DNA promotion evaluation."
                    )
                    self._notify(msg, f"gym_start:{session_id[:20]}")
                except Exception as e:
                    logger.warning(f"Failed to send pre-session notification: {e}")

            logger.info(f"Running scheduled approval gym session {session_id}")
            if self._approval_gym is None:
                logger.error("No ApprovalGym configured for session run.")
                return

            records = self._approval_gym.run_session(approval_twin=None)
            session_count = len(records) if records else 0

            self._log_session(
                {
                    "session_id": session_id,
                    "session_time": session_time.isoformat(),
                    "status": "completed",
                    "proposal_count": session_count,
                }
            )

            if self._telegram_notifier:
                try:
                    msg = (
                        f"Approval Gym Session Complete\nSession ID: {session_id}\nProposals Evaluated: {session_count}"
                    )
                    self._notify(msg, f"gym_done:{session_id[:20]}")
                except Exception as e:
                    logger.warning(f"Failed to send post-session notification: {e}")

            self._last_session_time = session_time

        except Exception as e:
            logger.error(f"Scheduled session {session_id} failed: {e}", exc_info=True)
            self._log_session(
                {
                    "session_id": session_id,
                    "session_time": session_time.isoformat(),
                    "status": "failed",
                    "error": str(e),
                }
            )

    def _log_session(self, session_record: dict[str, Any]) -> None:
        try:
            safe_append_jsonl(Path(self._history_path), session_record, hash_chain=False)
        except Exception as e:
            logger.error(f"Failed to log session: {e}")

    def get_last_session_time(self) -> Optional[datetime]:
        return self._last_session_time

    def get_next_session_time(self) -> Optional[datetime]:
        if self._last_session_time is None:
            return datetime.now(timezone.utc) + timedelta(hours=self._interval_hours)
        return self._last_session_time + timedelta(hours=self._interval_hours)

    def set_interval_hours(self, hours: int) -> None:
        with self._lock:
            self._interval_hours = max(1, int(hours))
            logger.info(f"Gym scheduler interval updated to {self._interval_hours}h")

    def is_running(self) -> bool:
        return self._running
