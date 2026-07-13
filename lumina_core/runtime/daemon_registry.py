"""Registry of runtime daemon threads for liveness checks and in-process recovery."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class DaemonEntry:
    name: str
    thread: threading.Thread
    target_factory: Callable[[], None] | None = None
    restart_count: int = 0


class RuntimeDaemonRegistry:
    """Process-scoped registry of daemon threads started during bootstrap."""

    _instance: RuntimeDaemonRegistry | None = None

    def __init__(self) -> None:
        self._entries: dict[str, DaemonEntry] = {}
        self._lock = threading.Lock()

    @classmethod
    def get(cls) -> RuntimeDaemonRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def register(
        self,
        name: str,
        thread: threading.Thread,
        *,
        target_factory: Callable[[], None] | None = None,
    ) -> None:
        with self._lock:
            self._entries[name] = DaemonEntry(
                name=name,
                thread=thread,
                target_factory=target_factory,
            )

    def is_alive(self, name: str) -> bool:
        with self._lock:
            entry = self._entries.get(name)
            if entry is None:
                return False
            return entry.thread.is_alive()

    def dead_daemons(self) -> list[str]:
        with self._lock:
            return [name for name, entry in self._entries.items() if not entry.thread.is_alive()]

    def get_entry(self, name: str) -> DaemonEntry | None:
        with self._lock:
            return self._entries.get(name)

    def restart_daemon(self, name: str, *, start_fn: Callable[[Callable[[], None], str | None], threading.Thread]) -> bool:
        """Restart a dead daemon using its stored target_factory."""
        with self._lock:
            entry = self._entries.get(name)
            if entry is None or entry.target_factory is None:
                return False
            factory = entry.target_factory
            entry.restart_count += 1

        new_thread = start_fn(factory, name)
        with self._lock:
            entry = self._entries.get(name)
            if entry is not None:
                entry.thread = new_thread
        return True

    def names(self) -> list[str]:
        with self._lock:
            return list(self._entries.keys())

    def snapshot(self) -> dict[str, dict[str, object]]:
        with self._lock:
            out: dict[str, dict[str, object]] = {}
            for name, entry in self._entries.items():
                out[name] = {
                    "alive": entry.thread.is_alive(),
                    "restart_count": entry.restart_count,
                    "daemon": entry.thread.daemon,
                }
            return out
