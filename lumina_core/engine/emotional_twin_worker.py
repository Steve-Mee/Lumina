"""
EmotionalTwinWorker — D2 sub-slice 16: emotional twin bootstrap from supervisor inner loop.

Background daemon thread; non-capital observability/learning path.
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

logger = logging.getLogger(__name__)


class EmotionalTwinWorker:
    """Bounded owner for emotional twin background cycle (D2 sub-slice 16)."""

    def __init__(self, *, app: Any, sleep_seconds: float = 60.0) -> None:
        self.app = app
        self.sleep_seconds = max(1.0, float(sleep_seconds))
        self._logger = getattr(app, "logger", logger)
        self._thread: threading.Thread | None = None

    def run_cycle_loop(self) -> None:
        """Blocking loop; intended for daemon thread target."""
        while True:
            try:
                twin = getattr(self.app, "emotional_twin_agent", None)
                if twin is not None and hasattr(twin, "run_cycle"):
                    twin.run_cycle()
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RUNTIME_TWIN_010",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                self._logger.error(f"EmotionalTwin cycle error: {exc}")
            time.sleep(self.sleep_seconds)

    def start_daemon_thread(self) -> threading.Thread | None:
        """Start background twin worker if agent present; return thread or None."""
        if getattr(self.app, "emotional_twin_agent", None) is None:
            return None
        self._thread = threading.Thread(
            target=self.run_cycle_loop,
            name="emotional-twin-worker",
            daemon=True,
        )
        self._thread.start()
        return self._thread
