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


class ReasoningPathsMixin:
    """Latency SLA, fast-path toggles, inference routing, and consensus paths."""

    __slots__ = ()

    def _set_fast_path_only(self, enabled: bool, reason: str) -> None:
        app = self._app()
        current = bool(getattr(app, "FAST_PATH_ONLY", False))
        if current == enabled:
            return
        setattr(app, "FAST_PATH_ONLY", enabled)
        state = "enabled" if enabled else "disabled"
        app.logger.warning(f"FAST_PATH_ONLY {state} (reasoning): {reason}")
        try:
            logger.info(
                "reasoning.fast_path_toggle",
                extra={"event_data": {"event": "reasoning.fast_path_toggle", "enabled": enabled, "reason": reason}},
            )
        except Exception:
            pass

    def _record_latency(self, elapsed_ms: float, source: str) -> None:
        app = self._app()
        if elapsed_ms > self.latency_sla_ms:
            self._sla_breach_streak += 1
            self._sla_recovery_streak = 0
            if self._sla_breach_streak >= 2:
                try:
                    logger.warning(
                        "reasoning.sla_breach",
                        extra={
                            "event_data": {
                                "event": "reasoning.sla_breach",
                                "source": source,
                                "elapsed_ms": elapsed_ms,
                                "sla_ms": self.latency_sla_ms,
                                "streak": self._sla_breach_streak,
                            }
                        },
                    )
                except Exception:
                    pass
                self._set_fast_path_only(
                    True,
                    f"{source} latency {elapsed_ms:.1f}ms above SLA {self.latency_sla_ms:.1f}ms",
                )
        else:
            self._sla_recovery_streak += 1
            self._sla_breach_streak = 0
            if self._sla_recovery_streak >= 4:
                self._set_fast_path_only(False, f"{source} latency recovered ({elapsed_ms:.1f}ms)")

        setattr(app, "REASONING_LATENCY_MS", round(float(elapsed_ms), 2))
        try:
            record_reasoning_latency_monitoring(
                source=source,
                elapsed_ms=float(elapsed_ms),
                sla_ms=float(self.latency_sla_ms),
                breach_streak=int(self._sla_breach_streak),
                fast_path_only=bool(getattr(app, "FAST_PATH_ONLY", False)),
                daily_pnl=float(getattr(self.engine, "realized_pnl_today", 0.0) or 0.0),
            )
        except Exception:
            pass

    def _fast_path_only_enabled(self) -> bool:
        app = self._app()
        return bool(getattr(app, "FAST_PATH_ONLY", False))

    def _session_trading_allowed(self) -> tuple[bool, str]:
        allowed, reason = session_guard_allows_trading(self.engine)
        return bool(allowed), str(reason)

    @staticmethod
    def _route_agent_styles(agent_styles: dict[str, str], snapshot: RegimeSnapshot) -> dict[str, str]:
        ordered_names = [name for name in snapshot.adaptive_policy.agent_route if name in agent_styles]
        if not ordered_names:
            ordered_names = list(agent_styles.keys())
        if snapshot.adaptive_policy.high_risk and "risk" in agent_styles and "risk" not in ordered_names:
            ordered_names.insert(0, "risk")
        if snapshot.adaptive_policy.high_risk:
            ordered_names = ordered_names[: max(1, min(2, len(ordered_names)))]
        return {name: agent_styles[name] for name in ordered_names}

    def infer_json(
        self,
        payload: dict[str, Any],
        timeout: int = 20,
        context: str = "xai_json",
        max_retries: int = 1,
        decision_context_id: str | None = None,
    ) -> dict[str, Any] | None:
        assert self.llm_client is not None
        assert self.llm_router is not None
        resolved_context_id = decision_context_id or self._new_decision_context_id(context)
        with correlation_id(resolved_context_id):
            if self._fast_path_only_enabled():
                llm_result = self.llm_client.complete_trading_json(
                    payload=payload,
                    timeout_seconds=1,
                    context=context,
                    max_retries=0,
                    decision_context_id=resolved_context_id,
                    forced_path="fast_rule",
                    fallback_reason="fast_path_only_enabled",
                )
                routed = self.llm_router.after_llm_call(llm_result, context=context)
                output = dict(routed.payload)
                output.setdefault("decision_context_id", llm_result.decision_context_id)
                output.setdefault("llm_path", llm_result.path)
                output.setdefault("routing_path", routed.routing_path)
                output.setdefault("llm_confidence", routed.llm_confidence)
                self._safe_structured_log(
                    logger,
                    logging.WARNING,
                    "reasoning.fast_path_fallback",
                    decision_context_id=resolved_context_id,
                    context=context,
                    reason="fast_path_only_enabled",
                )
                return output

            started = time.perf_counter()
            model_version = str(payload.get("model", "unknown"))
            llm_result = self.llm_client.complete_trading_json(
                payload=payload,
                timeout_seconds=timeout,
                context=context,
                max_retries=max_retries,
                decision_context_id=resolved_context_id,
            )
            elapsed_ms = (
                llm_result.latency_ms if llm_result.latency_ms > 0.0 else (time.perf_counter() - started) * 1000.0
            )
            routed = self.llm_router.after_llm_call(llm_result, context=context)
            result = dict(routed.payload)
            result.setdefault("decision_context_id", llm_result.decision_context_id)
            result.setdefault("llm_path", llm_result.path)
            result.setdefault("routing_path", routed.routing_path)
            result.setdefault("llm_confidence", routed.llm_confidence)
            self._record_latency(elapsed_ms, source=context)
            if logger.isEnabledFor(logging.DEBUG):
                self._safe_structured_log(
                    logger,
                    logging.DEBUG,
                    "reasoning.infer_json.latency",
                    decision_context_id=resolved_context_id,
                    context=context,
                    elapsed_ms=elapsed_ms,
                    prompt_preview=str(payload)[:300],
                    response_preview=str(result)[:300],
                )
            self._log_decision(
                agent_id="ReasoningService",
                raw_input=payload,
                raw_output=result,
                confidence=float(result.get("confidence", 0.0)),
                policy_outcome="inference_fallback" if llm_result.fallback else "inference_success",
                decision_context_id=llm_result.decision_context_id,
                model_version=model_version,
            )
            return result

    async def multi_agent_consensus(
        self,
        price: float,
        mtf_data: str,
        pa_summary: str,
        structure: dict[str, Any],
        fib_levels: dict[str, Any],
    ) -> dict[str, Any]:
        app = self._app()
        consensus_context_id = self._new_decision_context_id("multi_agent_consensus")
        blackboard = getattr(self.engine, "blackboard", None)
        if blackboard is not None and hasattr(blackboard, "latest"):
            topics = (
                "agent.news.proposal",
                "agent.tape.proposal",
                "agent.emotional_twin.proposal",
                "agent.rl.proposal",
                "agent.meta.proposal",
            )
            proposals: dict[str, Any] = {}
            for topic in topics:
                evt = blackboard.latest(topic)
                if evt is None:
                    continue
                payload = getattr(evt, "payload", {}) if hasattr(evt, "payload") else {}
                proposals[topic] = payload if isinstance(payload, dict) else {"raw": str(payload)}
            if proposals:
                self._safe_structured_log(
                    logger,
                    logging.DEBUG,
                    "reasoning.blackboard_proposals",
                    decision_context_id=consensus_context_id,
                    proposals=proposals,
                )
        session_allowed, session_reason = self._session_trading_allowed()
        if not session_allowed:
            self._set_fast_path_only(True, f"session_guard: {session_reason}")
            blocked = {
                "signal": "HOLD",
                "confidence": 0.35,
                "reason": f"Fast-path mode active: {session_reason}",
                "agent_votes": {},
                "regime": {"label": "SESSION_BLOCKED", "risk_state": "HIGH_RISK"},
                "decision_context_id": consensus_context_id,
                "llm_path": "fast_rule",
            }
            self._log_fast_rule_path(
                context="multi_agent_consensus",
                decision_context_id=consensus_context_id,
                reason=f"session_guard_blocked:{session_reason}",
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
                raw_output=blocked,
                confidence=float(blocked.get("confidence", 0.0)),
                policy_outcome="session_blocked",
                decision_context_id=consensus_context_id,
                model_version="reasoning-consensus-v1",
            )
            return blocked

        regime_snapshot = self.refresh_regime_snapshot(structure=structure)
        if self._fast_path_only_enabled():
            app.logger.info("MULTI_AGENT_CONSENSUS_SKIPPED,mode=fast_path_only")
            fast_path = {
                "signal": "HOLD",
                "confidence": 0.4,
                "reason": "Fast-path mode active due to latency SLA breach",
                "agent_votes": {},
                "regime": regime_snapshot.to_dict(),
                "decision_context_id": consensus_context_id,
                "llm_path": "fast_rule",
            }
            self._log_fast_rule_path(
                context="multi_agent_consensus",
                decision_context_id=consensus_context_id,
                reason="fast_path_only_enabled",
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
                raw_output=fast_path,
                confidence=float(fast_path.get("confidence", 0.0)),
                policy_outcome="fast_path_only",
                decision_context_id=consensus_context_id,
                model_version="reasoning-consensus-v1",
            )
            return fast_path

        get_dream = getattr(self.engine, "get_current_dream_snapshot", None)
        if callable(get_dream):
            dream_result = get_dream()
            if isinstance(dream_result, dict):
                current_confluence = float(dream_result.get("confluence_score", 0.0) or 0.0)
            else:
                current_confluence = 0.0
        else:
            current_confluence = 0.0
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
