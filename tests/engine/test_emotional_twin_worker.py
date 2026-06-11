"""Tests for EmotionalTwinWorker (D2 sub-slice 16)."""

from types import SimpleNamespace

import pytest

from lumina_core.engine.emotional_twin_worker import EmotionalTwinWorker


@pytest.mark.unit
def test_twin_worker_starts_thread_when_agent_present():
    cycles: list[str] = []

    class Twin:
        def run_cycle(self):
            cycles.append("ok")

    app = SimpleNamespace(emotional_twin_agent=Twin(), logger=SimpleNamespace(error=lambda *a, **k: None))
    worker = EmotionalTwinWorker(app=app, sleep_seconds=0.01)
    thread = worker.start_daemon_thread()
    assert thread is not None
    import time

    time.sleep(0.05)
    assert cycles
    print("MANUAL_SMOKE_SUB16_TWIN_SUCCESS")


@pytest.mark.unit
def test_supervisor_inner_no_inline_twin_while():
    from pathlib import Path

    facade = Path("lumina_core/engine/runtime_workers_facade.py").read_text(encoding="utf-8")
    assert "def _emotional_twin_worker" not in facade
    assert "EmotionalTwinWorker" in facade
    assert "while True:" in facade

    god = Path("lumina_core/runtime_workers.py").read_text(encoding="utf-8")
    assert "while True:" not in god
    assert "SupervisorLoopRunner" in god
