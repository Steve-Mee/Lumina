"""
UI Components - Status Badge
Reusable colored status badge for Streamlit.
"""

import html
from typing import Literal

Palette = {
    "available": "#0f766e",
    "blocked": "#b45309",
    "ready": "#1d4ed8",
    "warning": "#92400e",
    "neutral": "#374151",
    "success": "#16a34a",
    "error": "#dc2626",
}

def status_badge(label: str, status: Literal["available", "blocked", "ready", "warning", "neutral", "success", "error"] = "neutral") -> str:
    color = Palette.get(status, "#374151")
    safe_label = html.escape(label)
    return (
        f'<span style="display:inline-block; padding:0.2rem 0.55rem; border-radius:999px; '
        f'background:{color}; color:white; font-size:0.78rem; font-weight:600;">{safe_label}</span>'
    )
