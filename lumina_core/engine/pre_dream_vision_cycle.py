"""
PreDreamVisionCycleService — D2 sub-slice 22: vision/infer/post-process extraction from PreDreamDaemon.

Pre-gate surface: infer_json + TradingEngineExecutionAggregate publish or dream field updates.
Preserves producer="runtime_workers.pre_dream_daemon" and context="pre_dream_vision".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lumina_core.agent_orchestration.schemas import (
    TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
    TradingEngineExecutionAggregate,
    filter_payload_for_execution_aggregate,
)
from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PreDreamVisionCycleResult:
    should_continue: bool


class PreDreamVisionCycleService:
    """Bounded owner for pre-dream vision infer + dream apply (D2 sub-slice 22)."""

    def __init__(self, *, app: Any) -> None:
        self.app = app
        self._logger = getattr(app, "logger", logger)

    def run_cycle(
        self,
        *,
        consensus: dict[str, Any],
        meta: dict[str, Any],
        rl_context: str,
        past_experiences: Any,
        chart_base64: str,
        min_conf: float,
        macro_news_sentiment: str,
        macro_news_score: float,
        news_data: dict[str, Any],
        macro_news_multiplier: float,
        avoid_active: bool,
    ) -> PreDreamVisionCycleResult:
        """Build vision payload, infer, apply dream side-effects (verbatim from PreDreamDaemon.run)."""
        app = self.app
        vision_content = [
            {
                "type": "text",
                "text": f"""Multi-Agent Consensus: {consensus["signal"]} (conf {consensus["confidence"]:.2f})
RL Policy Bias: {rl_context}
Relevante ervaringen: {past_experiences}
Meta-reasoning: {meta.get("meta_reasoning", "")}
Counter-factuals: {meta.get("counterfactuals", [])}
World Model (Macro + Micro): 
Macro -> VIX {app.world_model["macro"]["vix"]:.1f}, DXY {app.world_model["macro"]["dxy"]:.1f}, 10y {app.world_model["macro"]["ten_year_yield"]:.2f}
Micro -> Regime {app.world_model["micro"]["regime"]}, Orderflow {app.world_model["micro"]["orderflow_bias"]}
News Sentiment: {macro_news_sentiment} (score {macro_news_score:.2f}, impact {news_data["impact"]})
News Multiplier: {macro_news_multiplier:.2f} | Avoidance Active: {str(avoid_active)}
Use this full world model as the basis for your decision.
Use RL Policy Bias as directional prior, not as absolute rule.
Return JSON only with: signal, confidence, stop, target, reason, why_no_trade, confluence_score, chosen_strategy, fib_levels_drawn, narrative_reasoning""",
            },
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{chart_base64}"}},
        ]

        payload = {
            "model": app.engine.config.vision_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are visually trained. Use all layers, including the dynamic world model.",
                },
                {"role": "user", "content": vision_content},
            ],
            "max_tokens": 1300,
        }

        dream_json = None
        infer_json_fn = getattr(app, "infer_json", None)
        if callable(infer_json_fn):
            dream_json = infer_json_fn(payload, timeout=50, context="pre_dream_vision")
        if dream_json is None:
            return PreDreamVisionCycleResult(should_continue=True)

        if isinstance(dream_json, dict):
            if avoid_active:
                dream_json["signal"] = "HOLD"
                dream_json["why_no_trade"] = "News avoidance window active"

            twin = getattr(app.engine, "emotional_twin", None)
            if twin is not None and hasattr(twin, "apply_correction"):
                dream_json = twin.apply_correction(dream_json)

            aggregate_confidence = float(max(min(dream_json.get("confluence_score", 0.0) or 0.0, 1.0), 0.0))
            dream_json["confluence_score"] = aggregate_confidence
            if dream_json.get("confidence") is None:
                dream_json["confidence"] = aggregate_confidence
            event_bus = getattr(getattr(app, "engine", None), "event_bus", None)
            if event_bus is not None and hasattr(event_bus, "publish"):
                filtered = filter_payload_for_execution_aggregate(dict(dream_json))
                TradingEngineExecutionAggregate.model_validate(filtered)
                event_bus.publish(
                    topic=TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
                    producer="runtime_workers.pre_dream_daemon",
                    payload=filtered,
                )
            else:
                app.set_current_dream_fields(dream_json)
            app.set_current_dream_value(
                "confluence_score", max(min_conf, consensus["confidence"], meta.get("meta_score", 0.5))
            )
            dream_snapshot = app.get_current_dream_snapshot()

            raw_fibs = dream_json.get("fib_levels_drawn", {})
            app.AI_DRAWN_FIBS = raw_fibs if isinstance(raw_fibs, dict) else {}
            narrative_reasoning = dream_json.get("narrative_reasoning", "")

            app.speak(narrative_reasoning)
            app.store_experience_to_vector_db(
                context=f"World Model Update + Dream: {narrative_reasoning[:150]}",
                metadata={"type": "world_model_dream", "date": datetime.now().isoformat()},
            )

            _mode_val = getattr(getattr(app, "engine", None), "config", None)
            _mode_val = getattr(_mode_val, "trade_mode", "paper") if _mode_val else "paper"
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message=(
                        f"🌍 v36 WORLD MODEL + META DREAM: "
                        f"{dream_snapshot.get('chosen_strategy')} → {dream_snapshot.get('signal')} "
                        f"(conf={dream_snapshot.get('confluence_score', 0):.2f})"
                    ),
                    context={"mode": _mode_val},
                )
            )

        return PreDreamVisionCycleResult(should_continue=False)
