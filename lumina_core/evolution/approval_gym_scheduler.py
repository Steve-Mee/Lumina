"""Scheduler for periodic DNA approval gymnasium sessions with Telegram integration."""

import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ApprovalGymScheduler:
    """Manages periodic DNA approval gym sessions with optional Telegram notifications.
    
    Architecture:
    - Singleton scheduler (one instance per app lifecycle)
    - Schedules gym sessions at configurable intervals (default 6 hours)
    - Optionally sends Telegram notifications before each session
    - Logs session history to disk for audit trail
    - Thread-safe with RLock
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
    ):
        """Initialize approval gym scheduler.
        
        Args:
            approval_gym: ApprovalGym instance for running sessions
            telegram_notifier: TelegramNotifier for optional notifications
            interval_hours: Hours between sessions (default 6)
            history_path: Path to session history log
        """
        if getattr(self, "_initialized", False):
            return

        self._approval_gym = approval_gym
        self._telegram_notifier = telegram_notifier
        self._interval_hours = max(1, int(interval_hours))  # Minimum 1 hour
        self._history_path = Path(history_path)
        self._history_path.parent.mkdir(parents=True, exist_ok=True)

        self._last_session_time: Optional[datetime] = None
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._initialized = True

    def start_scheduler(self) -> bool:
        """Start background scheduler thread (fail-closed: returns False if already running).
        
        Returns:
            True if scheduler started, False if already running or no gym configured
        """
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
        """Stop background scheduler thread.
        
        Returns:
            True if stopped, False if not running
        """
        with self._lock:
            if not self._running:
                logger.warning("Scheduler not running.")
                return False

            self._running = False
            logger.info("Approval Gym scheduler stopped.")
            return True

    def _scheduler_loop(self) -> None:
        """Background loop: run gym sessions at scheduled intervals."""
        logger.info(f"Scheduler loop started (interval: {self._interval_hours}h)")

        while self._running:
            try:
                # Calculate next session time
                now = datetime.now(timezone.utc)
                if self._last_session_time is None:
                    # First run: schedule for next interval
                    next_session = now + timedelta(hours=self._interval_hours)
                else:
                    next_session = self._last_session_time + timedelta(hours=self._interval_hours)

                wait_seconds = max(0, (next_session - now).total_seconds())

                if wait_seconds > 0:
                    logger.debug(f"Next gym session scheduled in {wait_seconds:.0f}s")
                    # Sleep in small chunks to allow quick shutdown
                    remaining = wait_seconds
                    while remaining > 0 and self._running:
                        sleep_chunk = min(1.0, remaining)
                        threading.Event().wait(sleep_chunk)
                        remaining -= sleep_chunk

                # Run session if scheduler still active
                if self._running:
                    self._run_scheduled_session()

            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
                # Continue running despite errors
                if self._running:
                    threading.Event().wait(5.0)  # Backoff before retry

    def _run_scheduled_session(self) -> None:
        """Execute a single scheduled approval gym session."""
        session_time = datetime.now(timezone.utc)
        session_id = session_time.isoformat()

        try:
            # Notify before session
            if self._telegram_notifier:
                try:
                    msg = (
                        f"🏋️ **Approval Gym Session Starting**\n"
                        f"Session ID: `{session_id}`\n"
                        f"Steve, prepare for DNA promotion evaluation."
                    )
                    self._telegram_notifier._send_telegram_message(msg)
                except Exception as e:
                    logger.warning(f"Failed to send pre-session notification: {e}")

            # Run session
            logger.info(f"Running scheduled approval gym session {session_id}")
            if self._approval_gym is None:
                logger.error("No ApprovalGym configured for session run.")
                return

            records = self._approval_gym.run_session(approval_twin=None)  # No RLHF trigger for scheduled sessions
            session_count = len(records) if records else 0

            # Log session to history
            self._log_session({
                "session_id": session_id,
                "session_time": session_time.isoformat(),
                "status": "completed",
                "proposal_count": session_count,
            })

            # Notify after session
            if self._telegram_notifier:
                try:
                    msg = (
                        f"✅ **Approval Gym Session Complete**\n"
                        f"Session ID: `{session_id}`\n"
                        f"Proposals Evaluated: {session_count}"
                    )
                    self._telegram_notifier._send_telegram_message(msg)
                except Exception as e:
                    logger.warning(f"Failed to send post-session notification: {e}")

            self._last_session_time = session_time

        except Exception as e:
            logger.error(f"Scheduled session {session_id} failed: {e}", exc_info=True)
            self._log_session({
                "session_id": session_id,
                "session_time": session_time.isoformat(),
                "status": "failed",
                "error": str(e),
            })

    def _log_session(self, session_record: dict[str, Any]) -> None:
        """Append session record to history log (audit trail).
        
        Args:
            session_record: Session metadata to log
        """
        try:
            import json
            with open(self._history_path, "a") as f:
                f.write(json.dumps(session_record) + "\n")
        except Exception as e:
            logger.error(f"Failed to log session: {e}")

    def get_last_session_time(self) -> Optional[datetime]:
        """Get timestamp of last completed session.
        
        Returns:
            datetime of last session, or None if no session run yet
        """
        return self._last_session_time

    def get_next_session_time(self) -> Optional[datetime]:
        """Estimate next scheduled session time.
        
        Returns:
            Estimated datetime of next session, or None if no session run yet
        """
        if self._last_session_time is None:
            return datetime.now(timezone.utc) + timedelta(hours=self._interval_hours)
        return self._last_session_time + timedelta(hours=self._interval_hours)

    def set_interval_hours(self, hours: int) -> None:
        """Dynamically update session interval.
        
        Args:
            hours: New interval in hours (minimum 1)
        """
        with self._lock:
            self._interval_hours = max(1, int(hours))
            logger.info(f"Gym scheduler interval updated to {self._interval_hours}h")

    def is_running(self) -> bool:
        """Check if scheduler is currently active.
        
        Returns:
            True if running, False otherwise
        """
        return self._running
