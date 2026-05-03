from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from .analysis_helpers import (
    build_pa_signature,
    calculate_dynamic_confluence,
    detect_market_regime,
    detect_market_structure,
    is_significant_event,
    parse_json_loose,
    run_async_safely,
    update_cost_tracker_from_usage,
)
from .engine_ports import SupportsAnalysis

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TechnicalAnalysisService:
    """Holds deterministic technical-analysis helpers and regime detection."""

    engine: SupportsAnalysis

    def detect_market_regime(self, df) -> str:
        regime_detector = getattr(self.engine, "regime_detector", None)
        if regime_detector is not None:
            try:
                structure = None
                if hasattr(df, "__len__") and len(df) >= 20:
                    structure = detect_market_structure(df)
                snapshot = regime_detector.detect(
                    df,
                    instrument=str(getattr(self.engine.config, "instrument", "MES JUN26")),
                    confluence_score=float(
                        self.engine.get_current_dream_snapshot().get("confluence_score", 0.0) or 0.0
                    ),
                    structure=structure,
                )
                self.engine.current_regime_snapshot = snapshot.to_dict()
                return snapshot.label
            except Exception:
                logger.exception("TechnicalAnalysisService failed to use regime_detector.detect; falling back")
        regime = detect_market_regime(df)
        self.engine.current_regime_snapshot = {
            "label": str(regime),
            "confidence": 0.5,
            "risk_state": "NORMAL",
            "adaptive_policy": {
                "fast_path_weight": 0.5,
                "agent_route": ["risk", "scalper", "swing"],
                "risk_multiplier": 1.0,
                "emotional_twin_sensitivity": 1.0,
                "cooldown_minutes": 30,
                "high_risk": False,
                "nightly_evolution_focus": str(regime).lower(),
            },
        }
        return regime

    def detect_market_structure(self, df) -> dict[str, Any]:
        return detect_market_structure(df)

    def calculate_dynamic_confluence(self, regime: str, recent_winrate: float) -> float:
        return calculate_dynamic_confluence(regime, recent_winrate)

    def is_significant_event(self, current_price: float, previous_price: float, regime: str) -> bool:
        return is_significant_event(current_price, previous_price, regime, self.engine.config.event_threshold)

    def update_cost_tracker_from_usage(self, usage: dict[str, Any] | None, channel: str = "reasoning") -> None:
        update_cost_tracker_from_usage(self.engine.cost_tracker, usage, channel)

    def run_async_safely(self, coro):
        return run_async_safely(coro)

    def parse_json_loose(self, raw_text: str) -> dict[str, Any]:
        return parse_json_loose(raw_text)

    def build_pa_signature(self, pa_summary: str) -> str:
        return build_pa_signature(pa_summary)
