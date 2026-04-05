from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .LocalInferenceEngine import LocalInferenceEngine
from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class ReasoningService:
    """Owns XAI interaction and higher-order reasoning workflows."""

    engine: LuminaEngine
    inference_engine: LocalInferenceEngine | None = None

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("ReasoningService requires a LuminaEngine")
        if self.inference_engine is None:
            self.inference_engine = LocalInferenceEngine(engine=self.engine)

    def _app(self):
        if self.engine.app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        return self.engine.app

    def infer_json(
        self,
        payload: dict[str, Any],
        timeout: int = 20,
        context: str = "xai_json",
        max_retries: int = 1,
    ) -> dict[str, Any] | None:
        assert self.inference_engine is not None
        return self.inference_engine.infer_json(
            payload,
            timeout=timeout,
            context=context,
            max_retries=max_retries,
        )

    async def multi_agent_consensus(
        self,
        price: float,
        mtf_data: str,
        pa_summary: str,
        structure: dict[str, Any],
        fib_levels: dict[str, Any],
    ) -> dict[str, Any]:
        app = self._app()
        agent_styles = self.engine.config.agent_styles
        agent_votes: dict[str, Any] = {}
        consistency_scores: list[float] = []

        for agent_name, style in agent_styles.items():
            payload = {
                "model": "grok-4.20-0309-reasoning",
                "messages": [
                    {
                        "role": "system",
                        "content": f"{style}\nGeef ALLEEN JSON met: signal (BUY/SELL/HOLD), confidence (0-1), reason (max 80 chars)",
                    },
                    {
                        "role": "user",
                        "content": f"""Huidige prijs: {price:.2f}
MTF: {mtf_data}
Price Action: {pa_summary}
Structure: BOS={structure.get('bos')}, CHOCH={structure.get('choch')}
Fibs: {fib_levels}
Wat is jouw trade-besluit?""",
                    },
                ],
                "max_tokens": 150,
                "temperature": 0.1,
            }

            try:
                vote = self.infer_json(payload, timeout=12, context=f"multi_agent_{agent_name}")
                if vote is not None:
                    agent_votes[agent_name] = vote
                    consistency_scores.append(float(vote.get("confidence", 0.5)))
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                app.logger.error(f"Multi-agent parse error ({agent_name}): {exc}")
                agent_votes[agent_name] = {"signal": "HOLD", "confidence": 0.3, "reason": "API error"}

            if agent_name not in agent_votes:
                agent_votes[agent_name] = {"signal": "HOLD", "confidence": 0.3, "reason": "Inference unavailable"}

        signals = [v.get("signal", "HOLD") for v in agent_votes.values()]
        most_common_signal = max(set(signals), key=signals.count) if signals else "HOLD"
        consistency = signals.count(most_common_signal) / max(1, len(signals))
        avg_confidence = sum(consistency_scores) / max(1, len(consistency_scores))
        consensus = {
            "signal": most_common_signal if consistency >= 0.67 else "HOLD",
            "confidence": round(avg_confidence * consistency, 2),
            "reason": f"Consensus van {list(agent_votes.keys())} | Consistency {consistency:.2f}",
            "agent_votes": agent_votes,
        }
        app.logger.info(f"MULTI_AGENT_CONSENSUS,signal={consensus['signal']},consistency={consistency:.2f}")
        return consensus

    async def meta_reasoning_and_counterfactuals(
        self,
        consensus: dict[str, Any],
        price: float,
        pa_summary: str,
        past_experiences: str,
    ) -> dict[str, Any]:
        app = self._app()
        payload = {
            "model": "grok-4.20-0309-reasoning",
            "messages": [
                {
                    "role": "system",
                    "content": """Je bent een strenge meta-trading coach. Geen emoties, alleen logica.
Voer de volgende twee stappen uit:
1. Meta-reasoning: Hoe goed was de huidige consensus? Wat zou een top-trader anders hebben gedaan?
2. Counter-factuals: Simuleer 3 alternatieven (geen trade, 2x groter, stop dichterbij) en geef de verwachte uitkomst.
Geef ALLEEN JSON met: meta_score (0-1), meta_reasoning (max 120 chars), counterfactuals (lijst van dicts)""",
                },
                {
                    "role": "user",
                    "content": f"""Huidige consensus: {consensus['signal']} (conf {consensus['confidence']:.2f})
Price Action: {pa_summary}
Relevante eerdere ervaringen: {past_experiences}
Prijs: {price:.2f}
Voer meta-reasoning + counter-factuals uit.""",
                },
            ],
            "max_tokens": 400,
            "temperature": 0.1,
        }

        try:
            meta = self.infer_json(payload, timeout=15, context="meta_reasoning")
            if meta is not None:
                app.logger.info(f"META_REASONING_COMPLETE,meta_score={meta.get('meta_score', 0.5):.2f}")
                return meta
        except Exception as exc:
            app.logger.error(f"Meta-reasoning error: {exc}")

        return {"meta_score": 0.6, "meta_reasoning": "Meta-reasoning niet gelukt", "counterfactuals": []}
