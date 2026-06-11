"""
PreDreamNewsCycleService — D2 sub-slice 21: news agent / fallback / proposal extraction from PreDreamDaemon.

Pre-proposal surface (observability + blackboard proposals with decision_context_id).
Preserves producer="runtime_workers.pre_dream_daemon" and Phase 2 Slice 12 lineage.
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PreDreamNewsCycleResult:
    cached_news_data: dict[str, Any]
    last_news_update_ts: float
    news_data: dict[str, Any]
    news_impact: float
    macro_news_sentiment: str
    macro_news_score: float
    macro_news_multiplier: float
    avoid_active: bool


class PreDreamNewsCycleService:
    """Bounded owner for pre-dream news cycle (D2 sub-slice 21)."""

    def __init__(self, *, app: Any) -> None:
        self.app = app
        self._logger = getattr(app, "logger", logger)

    def run_cycle(
        self,
        *,
        cycle_decision_context_id: str,
        cached_news_data: dict[str, Any],
        last_news_update_ts: float,
        blackboard: Any | None,
    ) -> PreDreamNewsCycleResult:
        """Run news agent / fallback paths and emit news proposals (verbatim from PreDreamDaemon.run)."""
        app = self.app
        news_agent = getattr(app, "news_agent", None)
        if news_agent is not None and hasattr(news_agent, "run_news_cycle"):
            try:
                news_cycle = news_agent.run_news_cycle()
                if isinstance(news_cycle, dict):
                    dynamic = news_cycle.get("dynamic_multipliers")
                    if isinstance(dynamic, dict) and dynamic:
                        app.engine.config.news_impact_multipliers = {str(k): float(v) for k, v in dynamic.items()}

                    cycle_news_data = news_cycle.get("news_data")
                    if isinstance(cycle_news_data, dict):
                        cached_news_data = cycle_news_data

                    avoid = bool(news_cycle.get("news_avoidance_window", False))
                    hold_until_ts = float(news_cycle.get("news_avoidance_hold_until_ts", 0.0) or 0.0)
                    if avoid and hold_until_ts > 0.0:
                        current_hold = float(app.get_current_dream_snapshot().get("hold_until_ts", 0.0) or 0.0)
                        news_updates = {
                            "hold_until_ts": max(current_hold, hold_until_ts),
                            "why_no_trade": str(news_cycle.get("news_avoidance_reason", "news_avoidance_window")),
                            "signal": "HOLD",
                            "decision_context_id": cycle_decision_context_id,
                        }
                        if blackboard is not None and hasattr(blackboard, "add_proposal"):
                            blackboard.add_proposal(
                                topic="agent.news.proposal",
                                producer="runtime_workers.pre_dream_daemon",
                                payload=news_updates,
                                confidence=float(news_cycle.get("confidence", 0.8) or 0.8),
                                correlation_id=cycle_decision_context_id,
                            )
                        else:
                            app.set_current_dream_fields(news_updates)

                    sentiment_signal = str(
                        news_cycle.get("sentiment_signal", cached_news_data.get("overall_sentiment", "neutral"))
                    )
                    sentiment_score = float(news_cycle.get("sentiment_score", 0.0) or 0.0)
                    dynamic_multiplier = float(news_cycle.get("dynamic_multiplier", 1.0) or 1.0)
                    world_model_news = {
                        "last_update": news_cycle.get("last_update"),
                        "overall_sentiment": sentiment_signal,
                        "sentiment_score": sentiment_score,
                        "impact": cached_news_data.get("impact", "medium"),
                        "events_count": len(cached_news_data.get("events", []))
                        if isinstance(cached_news_data.get("events", []), list)
                        else 0,
                        "multiplier": dynamic_multiplier,
                        "news_avoidance_window": avoid,
                    }
                    if isinstance(app.world_model, dict):
                        app.world_model["news"] = world_model_news
                        app.world_model.setdefault("macro", {})
                        app.world_model["macro"]["news_sentiment"] = sentiment_signal
                        app.world_model["macro"]["news_sentiment_score"] = sentiment_score
                        app.world_model["macro"]["news_multiplier"] = dynamic_multiplier
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RUNTIME_NEWS_006",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                (self._logger or logger).error(f"NewsAgent cycle error: {exc}")
        elif news_agent is not None and hasattr(news_agent, "run_cycle"):
            try:
                news_cycle = news_agent.run_cycle()
                if isinstance(news_cycle, dict):
                    cycle_news_data = news_cycle.get("news_data")
                    if isinstance(cycle_news_data, dict):
                        cached_news_data = cycle_news_data
            except Exception as exc:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RUNTIME_NEWS_007",
                    message=str(exc),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                (self._logger or logger).error(f"NewsAgent cycle error: {exc}")
        else:
            if time.time() - last_news_update_ts >= 60:
                cached_news_data = app.get_high_impact_news()
                last_news_update_ts = time.time()

        news_data = cached_news_data
        news_impact = app.resolve_news_multiplier(
            news_data, app.engine.config.news_impact_multipliers, default=1.0
        )
        if blackboard is not None and hasattr(blackboard, "add_proposal"):
            blackboard.add_proposal(
                topic="agent.news.proposal",
                producer="runtime_workers.pre_dream_daemon",
                payload={"news_impact": float(news_impact), "decision_context_id": cycle_decision_context_id},
                confidence=0.75,
                correlation_id=cycle_decision_context_id,
            )
        else:
            app.set_current_dream_value("news_impact", news_impact)

        macro_news_sentiment = "neutral"
        macro_news_score = 0.0
        macro_news_multiplier = float(news_impact)
        if isinstance(app.world_model, dict):
            macro = app.world_model.get("macro", {})
            if isinstance(macro, dict):
                macro_news_sentiment = str(macro.get("news_sentiment", macro_news_sentiment))
                macro_news_score = float(macro.get("news_sentiment_score", macro_news_score) or 0.0)
                macro_news_multiplier = float(
                    macro.get("news_multiplier", macro_news_multiplier) or macro_news_multiplier
                )

        avoid_active = bool(float(app.get_current_dream_snapshot().get("hold_until_ts", 0.0) or 0.0) > time.time())

        return PreDreamNewsCycleResult(
            cached_news_data=cached_news_data,
            last_news_update_ts=last_news_update_ts,
            news_data=news_data,
            news_impact=float(news_impact),
            macro_news_sentiment=macro_news_sentiment,
            macro_news_score=macro_news_score,
            macro_news_multiplier=macro_news_multiplier,
            avoid_active=avoid_active,
        )
