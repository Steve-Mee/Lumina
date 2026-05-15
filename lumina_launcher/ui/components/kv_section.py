"""
UI Components - KV Section
Reusable key-value renderer with optional help tooltips.
"""

import html
import streamlit as st
from typing import Any


def render_kv_section(
    title: str,
    rows: list[tuple[str, Any]],
    help_map: dict[str, str] | None = None,
) -> None:
    st.markdown(f"#### {title}")
    explanations = help_map or {}
    for label, value in rows:
        left, right = st.columns([1, 2])
        tip = explanations.get(label)
        if tip:
            safe_tip = html.escape(tip, quote=True)
            left.markdown(
                f'{label} <span title="{safe_tip}" style="display:inline-block;width:1rem;height:1rem;'
                f'line-height:1rem;text-align:center;border-radius:999px;border:1px solid #94a3b8;'
                f'color:#334155;font-size:0.72rem;margin-left:0.3rem;cursor:help;">?</span>',
                unsafe_allow_html=True,
            )
        else:
            left.caption(label)

        if isinstance(value, bool):
            from .status_badge import status_badge
            badge = status_badge("Yes", "available") if value else status_badge("No", "blocked")
            right.markdown(badge, unsafe_allow_html=True)
        else:
            right.markdown(str(value))
