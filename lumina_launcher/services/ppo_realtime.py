#!/usr/bin/env python3
"""
LUMINA PPO REAL-TIME STREAMING SERVICE
======================================

Production-grade WebSocket + file tailing for live PPO training monitoring.

Usage::

    from lumina_launcher.services.ppo_realtime import ppo_realtime_tailer

    ppo_realtime_tailer.start_watching()

    @router.websocket("/ws/ppo-evolution")
    async def ws_endpoint(websocket: WebSocket):
        await ppo_realtime_tailer.register_client(websocket)
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Set

from fastapi import WebSocket

from lumina_core.logging_utils import get_logger, resolve_monitoring_state_dir

logger = get_logger(__name__)


def _load_watchdog_modules():
    """Import PyPI ``watchdog`` even when repo-root ``watchdog.py`` shadows the name."""
    import importlib
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]

    for mod_name in list(sys.modules):
        if mod_name == "watchdog" or mod_name.startswith("watchdog."):
            mod = sys.modules.get(mod_name)
            mod_file = getattr(mod, "__file__", "") or ""
            if mod is not None and (not hasattr(mod, "__path__") or mod_file.endswith("watchdog.py")):
                del sys.modules[mod_name]

    filtered_path = [entry for entry in sys.path if Path(entry).resolve() != repo_root]
    previous_path = sys.path
    sys.path = filtered_path
    try:
        events_mod = importlib.import_module("watchdog.events")
        observers_mod = importlib.import_module("watchdog.observers")
    except ImportError as exc:
        raise RuntimeError(
            "watchdog is required for PPO realtime tailing. Install with: pip install watchdog"
        ) from exc
    finally:
        sys.path = previous_path
    return events_mod.FileSystemEventHandler, observers_mod.Observer


def _default_log_path() -> Path:
    return resolve_monitoring_state_dir() / "ppo_training_log.jsonl"


class PPORealtimeTailer:
    """Tail ``ppo_training_log.jsonl`` and broadcast new lines to WebSocket clients."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        self.log_path = Path(log_path) if log_path is not None else _default_log_path()
        self.clients: Set[WebSocket] = set()
        self.last_position = 0
        self._observer: Any | None = None
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def _resolved_log_path(self) -> Path:
        return self.log_path.expanduser().resolve()

    def _bind_loop(self) -> None:
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

    async def register_client(self, websocket: WebSocket) -> None:
        self._bind_loop()
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)
        await self._send_recent_lines(websocket, 40)

    def unregister_client(self, websocket: WebSocket) -> None:
        self.clients.discard(websocket)

    async def _send_recent_lines(self, websocket: WebSocket, n: int = 40) -> None:
        path = self._resolved_log_path()
        if not path.is_file():
            return
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines[-n:]:
                clean = line.strip()
                if clean:
                    await websocket.send_text(clean)
        except Exception:
            logger.warning("ppo_realtime.send_recent_lines_failed", exc_info=True)

    async def broadcast_new_line(self, line: str) -> None:
        """Broadcast a new log line to all connected clients."""
        clean = line.strip()
        if not clean:
            return
        disconnected: set[WebSocket] = set()
        async with self._lock:
            for client in list(self.clients):
                try:
                    await client.send_text(clean)
                except Exception:
                    disconnected.add(client)
            for client in disconnected:
                self.clients.discard(client)

    def start_watching(self, *, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Start file watcher in background thread (idempotent)."""
        if loop is not None:
            self._loop = loop
        if self._observer is not None:
            return

        try:
            FileSystemEventHandler, Observer = _load_watchdog_modules()
        except RuntimeError:
            logger.warning("ppo_realtime.watchdog_unavailable")
            return

        path = self._resolved_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            self.last_position = path.stat().st_size

        tailer = self

        class LogFileHandler(FileSystemEventHandler):
            def on_modified(self, event) -> None:
                if getattr(event, "is_directory", False):
                    return
                try:
                    changed = Path(str(event.src_path)).resolve()
                except OSError:
                    return
                if changed != path.resolve():
                    return
                tailer._schedule_process_new_lines()

        self._observer = Observer()
        self._observer.schedule(LogFileHandler(), str(path.parent), recursive=False)
        self._observer.start()
        logger.info("ppo_realtime.watching", extra={"event_data": {"path": str(path)}})

    def stop_watching(self) -> None:
        observer = self._observer
        self._observer = None
        if observer is None:
            return
        observer.stop()
        observer.join(timeout=5.0)
        logger.info("ppo_realtime.stopped")

    def _schedule_process_new_lines(self) -> None:
        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
                self._loop = loop
            except RuntimeError:
                logger.debug("ppo_realtime.no_event_loop_for_file_change")
                return

        def _run() -> None:
            asyncio.create_task(self._process_new_lines())

        loop.call_soon_threadsafe(_run)

    async def _process_new_lines(self) -> None:
        """Read and broadcast only new lines since last position."""
        path = self._resolved_log_path()
        if not path.is_file():
            return
        try:
            with path.open("r", encoding="utf-8") as handle:
                handle.seek(self.last_position)
                new_lines = handle.readlines()
                self.last_position = handle.tell()
            for line in new_lines:
                clean = line.strip()
                if clean:
                    await self.broadcast_new_line(clean)
        except Exception:
            logger.warning("ppo_realtime.process_new_lines_failed", exc_info=True)


ppo_realtime_tailer = PPORealtimeTailer()
