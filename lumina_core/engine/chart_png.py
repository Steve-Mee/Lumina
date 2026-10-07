"""In-memory PNG of the live NT chart.

Plotly's PNG export needs Kaleido. This path uses Matplotlib's Agg canvas,
which draws into bytes and does not open a window.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

_BG = "#0a0a0a"
_AX = "#111111"
_UP = "#00ff88"
_DOWN = "#ff4444"
_INK = "#d0d0d0"
_PANELS: tuple[tuple[str, str], ...] = (
    ("1min", "1min"),
    ("5min", "5min"),
    ("15min", "15min"),
    ("30min", "30min"),
    ("60min", "60min"),
    ("240min", "240min"),
)


def render_live_chart_png(
    frame: pd.DataFrame,
    *,
    title: str,
    frames_by_tf: dict[str, pd.DataFrame] | None = None,
) -> bytes:
    """Draw the six native NT timeframes. Missing TF is empty, never pandas-resampled."""
    fig = Figure(figsize=(14, 8), dpi=100, facecolor=_BG, layout="constrained")
    axes = fig.subplots(3, 2)
    flat = list(axes.flat)
    native = frames_by_tf or {}
    for ax, (name, _freq) in zip(flat, _PANELS, strict=True):
        ax.set_facecolor(_AX)
        panel = native.get(name)
        if panel is None or panel.empty:
            panel = frame.tail(80) if name == "1min" else None
        if panel is None:
            candles = pd.DataFrame(columns=["open", "high", "low", "close"])
        else:
            candles = panel.tail(80)
        _draw_candles(ax, candles)
        ax.set_title(name, color=_INK, fontsize=9)
        ax.tick_params(colors=_INK, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#2a2a2a")
        ax.set_xticks([])
    fig.suptitle(title, color=_UP, fontsize=11)
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    return buf.getvalue()


def _draw_candles(ax: Any, frame: pd.DataFrame) -> None:
    if frame.empty:
        ax.text(0.5, 0.5, "geen NT bars", color=_INK, ha="center", va="center", transform=ax.transAxes)
        return
    width = 0.6
    for i, row in enumerate(frame.itertuples(index=False)):
        open_px = float(row.open)
        close_px = float(row.close)
        high_px = float(row.high)
        low_px = float(row.low)
        color = _UP if close_px >= open_px else _DOWN
        ax.plot([i, i], [low_px, high_px], color=color, linewidth=0.8, solid_capstyle="round")
        body_low = min(open_px, close_px)
        body_h = abs(close_px - open_px)
        if body_h == 0.0:
            body_h = max((high_px - low_px) * 0.04, 1e-6)
        ax.add_patch(Rectangle((i - width / 2, body_low), width, body_h, facecolor=color, edgecolor=color))
    ax.set_xlim(-1, max(len(frame), 1))
