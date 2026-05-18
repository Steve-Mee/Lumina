"""Tests for Streamlit auto-refresh helper."""

from __future__ import annotations

from datetime import timedelta

import lumina_launcher.ui.auto_refresh as auto_refresh_module
from lumina_launcher.ui.auto_refresh import run_with_autorefresh


def test_run_with_autorefresh_invokes_render_when_disabled() -> None:
    calls: list[str] = []

    def _render() -> None:
        calls.append("ok")

    run_with_autorefresh(_render, enabled=False, interval_seconds=10)
    assert calls == ["ok"]


def test_run_with_autorefresh_uses_autorefresh_strategy(monkeypatch) -> None:
    calls: list[str] = []
    autorefresh_calls: list[tuple[int, str]] = []

    class _DummyStreamlit:
        def autorefresh(self, *, interval: int, key: str) -> None:
            autorefresh_calls.append((interval, key))

    def _render() -> None:
        calls.append("ok")

    monkeypatch.setattr(auto_refresh_module, "st", _DummyStreamlit())
    run_with_autorefresh(_render, enabled=True, interval_seconds=15, strategy="autorefresh")

    assert calls == ["ok"]
    assert autorefresh_calls == [(15_000, "lumina_autorefresh_tick")]


def test_run_with_autorefresh_uses_fragment_strategy(monkeypatch) -> None:
    calls: list[str] = []
    fragment_calls: list[timedelta] = []

    class _DummyStreamlit:
        def fragment(self, *, run_every: timedelta):
            fragment_calls.append(run_every)

            def _decorator(fn):
                return fn

            return _decorator

    def _render() -> None:
        calls.append("ok")

    monkeypatch.setattr(auto_refresh_module, "st", _DummyStreamlit())
    run_with_autorefresh(_render, enabled=True, interval_seconds=12, strategy="fragment")

    assert calls == ["ok"]
    assert fragment_calls == [timedelta(seconds=12)]
