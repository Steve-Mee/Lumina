"""FastAPI lifespan hooks for the OS backend."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lumina_launcher.services.ppo_realtime import ppo_realtime_tailer


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    ppo_realtime_tailer.start_watching(loop=asyncio.get_running_loop())
    yield
    ppo_realtime_tailer.stop_watching()
