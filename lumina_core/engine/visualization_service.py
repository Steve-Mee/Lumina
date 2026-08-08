from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


from .lumina_engine import LuminaEngine
from lumina_core.engine.visualization_charts import (
    VisualizationChartsMixin,
)


@dataclass(slots=True)
class VisualizationService(VisualizationChartsMixin):
    """Owns live screen-share state and compatibility dashboard launching."""

    engine: LuminaEngine
    dashboard_launcher: Callable[[], None] | None = None
    live_chart_window: Any = None
    latest_chart_image: Any = None
    chart_update_lock: threading.RLock = field(default_factory=threading.RLock)
    _tk_chart_queue: queue.Queue[tuple[Any, ...]] = field(default_factory=lambda: queue.Queue(maxsize=64))

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("VisualizationService requires a LuminaEngine")

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def start_dashboard(self) -> None:
        if self.dashboard_launcher is None:
            raise RuntimeError("VisualizationService.dashboard_launcher is not configured")
        self.dashboard_launcher()

