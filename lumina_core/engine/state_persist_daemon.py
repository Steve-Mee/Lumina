"""
StatePersistDaemon — D2 sub-slice 17: periodic runtime state persistence.

Independent cadence from supervisor loop latency.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any

logger = logging.getLogger(__name__)


class StatePersistDaemon:
    """Bounded owner for state_persist_daemon while-loop (D2 sub-slice 17)."""

    def __init__(self, *, app: Any, interval_seconds: int = 30) -> None:
        self.app = app
        self.interval_seconds = max(5, int(interval_seconds))
        self._logger = getattr(app, "logger", logger)

    def run(self) -> None:
        """Persist runtime state on a fixed cadence."""
        while True:
            try:
                self.app.save_state()
            except Exception as exc:
                self._logger.error(f"STATE_PERSIST_DAEMON_FAILED: {exc}\n{traceback.format_exc()}")
            time.sleep(self.interval_seconds)
