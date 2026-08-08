"""Fast-path / SLA / consensus path helpers mixed into ReasoningService."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from lumina_core.order_gatekeeper import session_guard_allows_trading
from lumina_core.risk.regime_detector import RegimeSnapshot
from .errors import format_error_code
from lumina_core.logging_utils import correlation_id, get_logger, record_reasoning_latency_monitoring

logger = get_logger("lumina.reasoning.service")


class ReasoningPathsInferTailMixin:
    """infer_json regime/consensus tail."""

    def _infer_json_regime_tail(
        self,
        *,
        app: Any,
        payload: dict[str, Any],
        context: str,
        timeout: int,
        max_retries: int,
        resolved_context_id: str,
        regime_snapshot: Any,
        current_confluence: float,
        consensus_context_id: str,
    ) -> dict[str, Any] | None:
        if regime_snapshot.adaptive_policy.high_risk and current_confluence < 0.88:
            app.logger.warning(
                "REGIME_CONSERVATIVE_HOLD,regime=%s,confluence=%.2f",
                regime_snapshot.label,
                current_confluence,
            )
            conservative = {
                "signal": "HOLD",
                "confidence": round(max(0.35, regime_snapshot.confidence * 0.7), 2),
                "reason": f"High-risk regime {regime_snapshot.label} forced conservative hold",
                "agent_votes": {},
                "regime": regime_snapshot.to_dict(),
                "decision_context_id": consensus_context_id,
                "llm_path": "fast_rule",
            }
            self._log_fast_rule_path(
                context="multi_agent_consensus",
                decision_context_id=consensus_context_id,
                reason=f"high_risk_regime:{regime_snapshot.label}",
            )
            self._log_decision(
                agent_id="ReasoningService",
                raw_input={
                    "price": price,
                    "mtf_data": mtf_data,
                    "pa_summary": pa_summary,
                    "structure": structure,
                    "fib_levels": fib_levels,
                },
                raw_output=conservative,
                confidence=float(conservative.get("confidence", 0.0)),
                policy_outcome="high_risk_hold",
                decision_context_id=consensus_context_id,
                model_version="reasoning-consensus-v1",
            )
            return conservative

        agent_styles = self._route_agent_styles(self.engine.config.agent_styles, regime_snapshot)
        agent_votes: dict[str, Any] = {}
        weighted_signals: dict[str, float] = {}
        weighted_confidence = 0.0
        total_weight = 0.0

        for idx, (agent_name, style) in enumerate(agent_styles.items()):
            weight = max(0.55, 1.0 - (idx * 0.12))
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
Structure: BOS={structure.get("bos")}, CHOCH={structure.get("choch")}
Fibs: {fib_levels}
Wat is jouw trade-besluit?""",
                    },
                ],
                "max_tokens": 150,
                "temperature": 0.1,
            }

            try:
                vote = self.infer_json(
                    payload,
                    timeout=12,
                    context=f"multi_agent_{agent_name}",
                    decision_context_id=f"{consensus_context_id}:{agent_name}",
                )
                if vote is not None:
                    agent_votes[agent_name] = vote
                    signal = str(vote.get("signal", "HOLD") or "HOLD").upper()
                    confidence = float(vote.get("confidence", 0.5) or 0.5)
                    weighted_signals[signal] = weighted_signals.get(signal, 0.0) + weight
                    weighted_confidence += confidence * weight
                    total_weight += weight
            except (json.JSONDecodeError, KeyError, TypeError, TimeoutError, RuntimeError, ValueError) as exc:
                app.logger.error(f"Multi-agent parse error ({agent_name}): {exc}")
                agent_votes[agent_name] = {"signal": "HOLD", "confidence": 0.3, "reason": "API error"}

            if agent_name not in agent_votes:
                agent_votes[agent_name] = {"signal": "HOLD", "confidence": 0.3, "reason": "Inference unavailable"}
                weighted_signals["HOLD"] = weighted_signals.get("HOLD", 0.0) + weight * 0.7
                weighted_confidence += 0.3 * weight
                total_weight += weight

        most_common_signal = max(weighted_signals, key=lambda x: weighted_signals[x]) if weighted_signals else "HOLD"
        top_weight = weighted_signals.get(most_common_signal, 0.0)
        consistency = top_weight / max(total_weight, 1e-9)
        avg_confidence = weighted_confidence / max(total_weight, 1e-9)
        consensus = {
            "signal": most_common_signal if consistency >= 0.67 else "HOLD",
            "confidence": round(avg_confidence * consistency, 2),
            "reason": f"Consensus van {list(agent_votes.keys())} | Consistency {consistency:.2f}",
            "agent_votes": agent_votes,
            "regime": regime_snapshot.to_dict(),
            "decision_context_id": consensus_context_id,
        }
        app.logger.info(
            "MULTI_AGENT_CONSENSUS,signal=%s,consistency=%.2f,regime=%s",
            consensus["signal"],
            consistency,
            regime_snapshot.label,
        )
        obs = self._observability_service()
        if obs is not None and hasattr(obs, "record_model_decision"):
            try:
                obs.record_model_decision(
                    agent="reasoning_consensus",
                    abstained=str(consensus.get("signal", "HOLD")).upper() == "HOLD",
                )
            except Exception:
                logger.exception("ReasoningService failed to record model decision metric")
        self._log_decision(
            agent_id="ReasoningService",
            raw_input={
                "price": price,
                "mtf_data": mtf_data,
                "pa_summary": pa_summary,
                "structure": structure,
                "fib_levels": fib_levels,
            },
            raw_output=consensus,
            confidence=float(consensus.get("confidence", 0.0)),
            policy_outcome="consensus_generated",
            decision_context_id=consensus_context_id,
            model_version="reasoning-consensus-v1",
        )
        return consensus

    async def meta_reasoning_and_counterfactuals(
        self,
        consensus: dict[str, Any],
        price: float,
        pa_summary: str,
        past_experiences: str,
    ) -> dict[str, Any]:
        app = self._app()
        if self._fast_path_only_enabled():
            return {
                "meta_score": 0.5,
                "meta_reasoning": "Skipped: fast-path mode active",
                "counterfactuals": [],
            }
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
                    "content": f"""Huidige consensus: {consensus["signal"]} (conf {consensus["confidence"]:.2f})
Price Action: {pa_summary}
Relevante eerdere ervaringen: {past_experiences}
Prijs: {price:.2f}
Voer meta-reasoning + counter-factuals uit.""",
                },
            ],
            "max_tokens": 400,
            "temperature": 0.1,
        }
        meta_context_id = self._new_decision_context_id("meta_reasoning")

        try:
            meta = self.infer_json(
                payload,
                timeout=15,
                context="meta_reasoning",
                decision_context_id=meta_context_id,
            )
            if meta is not None:
                app.logger.info(f"META_REASONING_COMPLETE,meta_score={meta.get('meta_score', 0.5):.2f}")
                self._log_decision(
                    agent_id="ReasoningService",
                    raw_input={
                        "consensus": consensus,
                        "price": price,
                        "pa_summary": pa_summary,
                        "past_experiences": past_experiences,
                    },
                    raw_output=meta,
                    confidence=float(meta.get("meta_score", 0.0)),
                    policy_outcome="meta_reasoning_success",
                    decision_context_id=str(meta.get("decision_context_id", meta_context_id)),
                    model_version="grok-4.20-0309-reasoning",
                )
                return meta
        except (json.JSONDecodeError, KeyError, TypeError, TimeoutError, RuntimeError, ValueError) as exc:
            code = format_error_code("REASONING_META", exc, fallback="FAILED")
            app.logger.error(f"Meta-reasoning error [{code}]: {exc}")

        fallback = {"meta_score": 0.6, "meta_reasoning": "Meta-reasoning niet gelukt", "counterfactuals": []}
        self._log_decision(
            agent_id="ReasoningService",
            raw_input={
                "consensus": consensus,
                "price": price,
                "pa_summary": pa_summary,
                "past_experiences": past_experiences,
            },
            raw_output=fallback,
            confidence=float(fallback.get("meta_score", 0.0)),
            policy_outcome="meta_reasoning_fallback",
            decision_context_id=meta_context_id,
            model_version="grok-4.20-0309-reasoning",
        )
        return fallback


__all__ = ["ReasoningPathsMixin"]

