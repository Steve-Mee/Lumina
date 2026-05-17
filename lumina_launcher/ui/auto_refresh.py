"""Streamlit auto-refresh helper (works on Streamlit versions without st.autorefresh)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import streamlit as st


def run_with_autorefresh(
    render_fn: Callable[[], None],
    *,
    enabled: bool,
    interval_seconds: int = 10,
) -> None:
    """Re-run ``render_fn`` on a timer when enabled."""
    if not enabled:
        render_fn()
        return
    if hasattr(st, "fragment"):
        @st.fragment(run_every=timedelta(seconds=interval_seconds))
        def _fragment_body() -> None:
            render_fn()

        _fragment_body()
        return
    if hasattr(st, "autorefresh"):
        st.autorefresh(interval=int(interval_seconds * 1000), key="lumina_autorefresh_tick")
        render_fn()
        return
    render_fn()
