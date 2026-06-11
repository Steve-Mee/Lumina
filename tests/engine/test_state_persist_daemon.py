"""Tests for StatePersistDaemon (D2 sub-slice 17)."""

from types import SimpleNamespace

import pytest

from lumina_core.engine.state_persist_daemon import StatePersistDaemon


@pytest.mark.unit
def test_state_persist_daemon_saves_and_stops(monkeypatch):
    saves: list[str] = []
    app = SimpleNamespace(
        save_state=lambda: saves.append("saved"),
        logger=SimpleNamespace(error=lambda *a, **k: None),
    )
    n = {"i": 0}

    def _sleep(_s):
        n["i"] += 1
        if n["i"] >= 2:
            raise StopIteration()

    monkeypatch.setattr("lumina_core.engine.state_persist_daemon.time.sleep", _sleep)
    with pytest.raises(StopIteration):
        StatePersistDaemon(app=app, interval_seconds=5).run()
    assert len(saves) >= 2
    print("MANUAL_SMOKE_SUB17_STATE_PERSIST_SUCCESS")


@pytest.mark.unit
def test_runtime_workers_state_persist_thin():
    from pathlib import Path

    text = Path("lumina_core/runtime_workers.py").read_text(encoding="utf-8")
    assert "StatePersistDaemon" in text
    block = text.split("def state_persist_daemon")[1].split("\ndef ")[0]
    assert "while True" not in block
