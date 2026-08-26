"""_run_async must not nest into a live asyncio loop (uvicorn/FastAPI)."""

from __future__ import annotations

import asyncio

import pytest

from lumina_core.engine.analysis_helpers import run_async_safely
from lumina_core.notifications.telegram_notifier import _run_async


async def _add(a: int, b: int) -> int:
    await asyncio.sleep(0)
    return a + b


def test_run_async_without_running_loop() -> None:
    assert _run_async(_add(2, 3)) == 5


def test_run_async_inside_running_loop() -> None:
    async def _outer() -> int:
        # Mimic FastAPI request handler calling sync Telegram send.
        return _run_async(_add(10, 7))

    assert asyncio.run(_outer()) == 17


def test_run_async_safely_inside_running_loop() -> None:
    async def _outer() -> int:
        return run_async_safely(_add(1, 1))

    assert asyncio.run(_outer()) == 2


def test_run_async_propagates_errors() -> None:
    async def _boom() -> None:
        raise ValueError("telegram down")

    with pytest.raises(ValueError, match="telegram down"):
        _run_async(_boom())
