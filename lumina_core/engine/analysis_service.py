from __future__ import annotations
import logging

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

import pandas as pd

from .fast_path_engine import FastPathEngine
from .errors import format_error_code
from .lumina_engine import LuminaEngine
from lumina_core.logging_utils import log_event, log_runtime_trace, runtime_trace_enabled
from lumina_core.engine.analysis_loop import HumanAnalysisLoopMixin


@dataclass(slots=True)
class HumanAnalysisService(HumanAnalysisLoopMixin):
    """Event-driven analysis loop extracted from legacy runtime globals."""

    engine: LuminaEngine
    last_5min_candle: Any = None
    cache_lock: threading.RLock = field(default_factory=threading.RLock)
    cache_ttl_seconds: int = 300
    last_deep_analysis: dict[str, Any] = field(
        default_factory=lambda: {
            "timestamp": None,
            "price": 0.0,
            "regime": "NEUTRAL",
            "pa_hash": "",
            "consensus": None,
            "meta": None,
            "ai_fibs": {},
            "vision_summary": "",
            "chart_base64": None,
            "swing_high": 0.0,
            "swing_low": 0.0,
        }
    )
    fast_path_engine: FastPathEngine | None = None
    ppo_trainer: Any | None = None

    def __post_init__(self) -> None:
        if self.fast_path_engine is None:
            self.fast_path_engine = FastPathEngine(engine=self.engine)
        if self.ppo_trainer is None:
            try:
                from lumina_core.engine.canonical_training import PPOTrainer

                self.ppo_trainer = PPOTrainer(engine=self.engine)
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/analysis_service.py:51")
                self.ppo_trainer = None

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to a runtime app")
        return self.engine.app

    def _cost_tracker(self) -> dict[str, Any]:
        return self.engine.cost_tracker

    def is_cache_valid(self, current_price: float, current_regime: str, pa_summary: str) -> bool:
        with self.cache_lock:
            ts = self.last_deep_analysis["timestamp"]
            if ts is None:
                return False
            time_diff = (datetime.now() - ts).total_seconds()
            last_price = float(self.last_deep_analysis["price"])
            price_change = abs(current_price - last_price) / last_price if last_price > 0 else 1.0
            pa_hash = str(hash(pa_summary))[:12]
            return (
                time_diff < self.cache_ttl_seconds
                and price_change < float(self.engine.config.event_threshold)
                and current_regime == self.last_deep_analysis["regime"]
                and pa_hash == self.last_deep_analysis["pa_hash"]
            )




AnalysisService = HumanAnalysisService
