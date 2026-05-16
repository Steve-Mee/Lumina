"""Tests for Streamlit auto-refresh helper."""

from __future__ import annotations

from lumina_launcher.ui.auto_refresh import run_with_autorefresh


def test_run_with_autorefresh_invokes_render_when_disabled() -> None:
    calls: list[str] = []

    def _render() -> None:
        calls.append("ok")

    run_with_autorefresh(_render, enabled=False, interval_seconds=10)
    assert calls == ["ok"]
