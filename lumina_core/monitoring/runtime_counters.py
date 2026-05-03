from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _default_cost_tracker() -> dict[str, Any]:
    return {
        "today": 0.0,
        "reasoning_tokens": 0,
        "vision_tokens": 0,
        "cached_analyses": 0,
    }


@dataclass(slots=True)
class RuntimeCounters:
    """Operational counters kept outside LuminaEngine core orchestration."""

    cost_tracker: dict[str, Any] = field(default_factory=_default_cost_tracker)
    rate_limit_backoff_seconds: int = 0
    restart_count: int = 0
    dashboard_last_chart_ts: float = 0.0
    dashboard_last_has_image: bool = False
