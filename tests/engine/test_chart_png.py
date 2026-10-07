"""The live screen-share chart must render without Kaleido."""
from __future__ import annotations

import pandas as pd

from lumina_core.engine.chart_png import render_live_chart_png


def test_render_live_chart_png_is_a_png() -> None:
    index = pd.date_range("2026-10-01 09:30", periods=40, freq="1min")
    frame = pd.DataFrame(
        {
            "open": [100 + i * 0.25 for i in range(40)],
            "high": [101 + i * 0.25 for i in range(40)],
            "low": [99 + i * 0.25 for i in range(40)],
            "close": [100.5 + i * 0.25 for i in range(40)],
        },
        index=index,
    )
    png = render_live_chart_png(frame, title="LUMINA · MES DEC26")
    assert png.startswith(b"\x89PNG")
    assert len(png) > 1000


def test_screen_share_photo_accepts_the_image(monkeypatch) -> None:
    from lumina_core.engine.visualization_charts import VisualizationChartsMixin

    seen: dict[str, object] = {}

    def fake_photo(image: object) -> str:
        seen["image"] = image
        return "photo"

    monkeypatch.setattr("PIL.ImageTk.PhotoImage", fake_photo)
    assert VisualizationChartsMixin()._create_photo_image("img") == "photo"
    assert seen["image"] == "img"
