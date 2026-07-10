"""Container shutdown wires maturation autopilot stop."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
def test_register_cleanup_stops_maturation_autopilot(monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.container import ApplicationContainer

    calls: list[str] = []

    def _stop() -> None:
        calls.append("stopped")

    monkeypatch.setattr(
        "lumina_core.maturity.autopilot.stop_maturation_autopilot",
        _stop,
    )
    monkeypatch.setattr("atexit.register", lambda fn: fn())

    container = object.__new__(ApplicationContainer)
    container.trade_reconciler = None
    container.observability_service = MagicMock()
    container.tts_engine = None
    container.broker = MagicMock()
    container.logger = MagicMock()

    container._register_cleanup()
    assert calls == ["stopped"]