"""Champion-safe MDS fan-out — drop-oldest on challenger, never block champion (K5)."""

from __future__ import annotations

import queue
from typing import Any


class ChampionSafeFanout:
    """Champion publish path is non-blocking. Challenger may lose ticks."""

    def __init__(self, capacity: int = 64) -> None:
        self._capacity = max(1, int(capacity))
        self._q: queue.Queue[Any] = queue.Queue(maxsize=self._capacity)
        self.dropped = 0

    def publish_to_challenger(self, tick: Any) -> None:
        try:
            self._q.put_nowait(tick)
            return
        except queue.Full:
            pass
        try:
            self._q.get_nowait()
            self.dropped += 1
        except queue.Empty:
            pass
        try:
            self._q.put_nowait(tick)
        except queue.Full:
            self.dropped += 1

    def get_challenger(self) -> Any | None:
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def qsize(self) -> int:
        return int(self._q.qsize())
