"""Sentinel Agent — observe→contain for network/token domain (ADR-0041).

Runs as a lightweight service tick. Never places orders, never mutates strategy
DNA, never arms REAL. Containment is network/token only.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

from lumina_core.cyber_sentinel import (
    is_containment_active,
    is_sentinel_active,
    read_containment,
    status_snapshot,
)

logger = logging.getLogger(__name__)

_agent_lock = threading.Lock()
_agent: "SentinelAgent | None" = None


class SentinelAgent:
    """Process-scoped Sentinel agent (singleton)."""

    def __init__(self, *, workspace_root: Path | None = None) -> None:
        self.workspace_root = workspace_root or Path(
            __import__("os").getenv("LUMINA_WORKSPACE") or "."
        ).resolve()
        self._started = False
        self._ticks = 0
        self._last_status: dict[str, Any] = {}

    def start(self) -> None:
        self._started = True
        logger.info(
            "sentinel_agent.start workspace=%s active_flag=%s",
            self.workspace_root,
            is_sentinel_active(),
        )
        self.tick()

    def stop(self) -> None:
        self._started = False
        logger.info("sentinel_agent.stop ticks=%s", self._ticks)

    def tick(self) -> dict[str, Any]:
        """One evaluation cycle — status only; events already push containment."""
        self._ticks += 1
        snap = status_snapshot(self.workspace_root)
        snap["ticks"] = self._ticks
        snap["started"] = self._started
        snap["observed_at_unix"] = time.time()
        # Never touch capital path even if containment is active.
        snap["trade_actions"] = []
        snap["capital_path"] = "untouched"
        self._last_status = snap
        if is_containment_active(self.workspace_root):
            c = read_containment(self.workspace_root)
            logger.warning(
                "sentinel_agent.tick containment_active code=%s reason=%s",
                c.code,
                c.reason,
            )
        return snap

    @property
    def last_status(self) -> dict[str, Any]:
        return dict(self._last_status)


def get_sentinel_agent(*, workspace_root: Path | None = None) -> SentinelAgent:
    global _agent
    with _agent_lock:
        if _agent is None:
            _agent = SentinelAgent(workspace_root=workspace_root)
        return _agent


def start_sentinel_agent(*, workspace_root: Path | None = None) -> SentinelAgent:
    agent = get_sentinel_agent(workspace_root=workspace_root)
    agent.start()
    return agent
