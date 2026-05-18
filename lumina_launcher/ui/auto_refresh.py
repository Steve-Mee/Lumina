"""Streamlit auto-refresh helper (works on Streamlit versions without st.autorefresh)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Literal

import streamlit as st


def run_with_autorefresh(
    render_fn: Callable[[], None],
    *,
    enabled: bool,
    interval_seconds: int = 10,
    strategy: Literal["fragment", "autorefresh", "auto"] = "auto",
) -> None:
    """Re-run ``render_fn`` on a timer when enabled."""
    if not enabled:
        render_fn()
        return
    use_autorefresh = strategy == "autorefresh" or (
        strategy == "auto" and hasattr(st, "autorefresh")
    )
    use_fragment = strategy == "fragment" or (
        strategy == "auto" and not use_autorefresh and hasattr(st, "fragment")
    )
    if use_autorefresh and hasattr(st, "autorefresh"):
        st.autorefresh(interval=int(interval_seconds * 1000), key="lumina_autorefresh_tick")
        render_fn()
        return
    if use_fragment and hasattr(st, "fragment"):
        @st.fragment(run_every=timedelta(seconds=interval_seconds))
        def _fragment_body() -> None:
            render_fn()

        _fragment_body()
        return
    render_fn()
