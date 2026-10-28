"""Maturity progress must not stall the API event loop."""

from __future__ import annotations

import asyncio
import time

from lumina_os.backend import maturity_endpoints as mod


def test_maturity_progress_yields_the_loop_while_scanning(monkeypatch) -> None:
    def slow() -> dict[str, object]:
        time.sleep(0.4)
        return {"ok": True}

    monkeypatch.setattr(mod, "_maturation_progress_payload", slow)

    async def race() -> tuple[float, dict[str, object]]:
        started = time.perf_counter()
        task = asyncio.create_task(mod.get_maturation_progress())
        await asyncio.sleep(0.05)
        elapsed = time.perf_counter() - started
        result = await task
        return elapsed, result

    elapsed, result = asyncio.run(race())
    assert elapsed < 0.2
    assert result["ok"] is True
