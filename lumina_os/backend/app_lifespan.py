"""FastAPI lifespan hooks for the OS backend."""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from lumina_launcher.services.ppo_realtime import ppo_realtime_tailer

logger = logging.getLogger(__name__)


async def _sentinel_tick_loop(workspace_root: Path, interval_s: float = 30.0) -> None:
    """Periodic SentinelAgent tick — observe/status only (no trade path)."""
    try:
        from lumina_core.sentinel_agent import get_sentinel_agent, start_sentinel_agent

        start_sentinel_agent(workspace_root=workspace_root)
        agent = get_sentinel_agent(workspace_root=workspace_root)
    except Exception:
        logger.warning("sentinel tick loop: agent unavailable", exc_info=True)
        return
    while True:
        try:
            agent.tick()
        except Exception:
            logger.warning("sentinel tick failed", exc_info=True)
        await asyncio.sleep(max(5.0, interval_s))


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    ppo_realtime_tailer.start_watching(loop=asyncio.get_running_loop())
    root = Path(os.getenv("LUMINA_WORKSPACE") or Path(__file__).resolve().parents[2])
    tick_task: asyncio.Task[None] | None = None
    try:
        interval = float(os.getenv("LUMINA_SENTINEL_TICK_SEC", "30") or 30)
        tick_task = asyncio.create_task(_sentinel_tick_loop(root, interval_s=interval))
    except Exception:
        logger.warning("Could not start sentinel tick loop", exc_info=True)
    try:
        yield
    finally:
        if tick_task is not None:
            tick_task.cancel()
            try:
                await tick_task
            except asyncio.CancelledError:
                pass
        ppo_realtime_tailer.stop_watching()
