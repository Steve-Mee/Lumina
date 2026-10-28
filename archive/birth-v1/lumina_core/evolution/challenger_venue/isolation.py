"""Fault boundary + optional own process for challenger venue (K4)."""

from __future__ import annotations

import logging
import multiprocessing
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChampionHeartbeat:
    beats: int = 0

    def beat(self) -> int:
        self.beats += 1
        return self.beats

    @property
    def alive(self) -> bool:
        return self.beats > 0


def run_with_fault_boundary(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Venue exceptions never propagate into champion tick."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        logger.exception("challenger_venue.fault_boundary")
        return None


def spawn_venue_process(target: Callable[..., Any], *args: Any) -> multiprocessing.Process:
    proc = multiprocessing.Process(target=target, args=args, daemon=True)
    proc.start()
    return proc


def venue_crash_worker() -> None:
    """Picklable worker that dies — used by K4 isolation tests."""
    import os

    os._exit(1)


def venue_process_main(workspace: str, queue: Any) -> None:
    """Picklable REAL-champion venue worker. Exceptions stay in this process."""
    from lumina_core.evolution.challenger_venue.runtime import VenueRuntime

    runtime = VenueRuntime(workspace)
    while True:
        try:
            tick = queue.get(timeout=0.5)
        except Exception:
            continue
        if tick is None:
            return
        try:
            runtime.on_tick(tick)
        except Exception:
            continue


def require_own_process(*, real_champion: bool, configured: bool = True) -> bool:
    return bool(real_champion and configured)
