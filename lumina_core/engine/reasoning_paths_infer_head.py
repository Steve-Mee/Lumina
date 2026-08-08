"""Fast-path / SLA / consensus path helpers mixed into ReasoningService."""

from __future__ import annotations

import logging
import time
from typing import Any

from lumina_core.logging_utils import correlation_id, get_logger
from lumina_core.engine.reasoning_paths_latency import ReasoningPathsLatencyMixin

logger = get_logger("lumina.reasoning.service")


class ReasoningPathsInferHeadMixin(ReasoningPathsLatencyMixin):
    """infer_json head (setup + early returns)."""

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
        return self._infer_json_regime_tail(
            app=app,
            payload={
                "price": price,
                "mtf_data": mtf_data,
                "pa_summary": pa_summary,
                "structure": structure,
                "fib_levels": fib_levels,
            },
            context="multi_agent_consensus",
            timeout=20,
            max_retries=1,
            resolved_context_id=consensus_context_id,
            regime_snapshot=regime_snapshot,
            current_confluence=current_confluence,
            consensus_context_id=consensus_context_id,
            price=price,
            mtf_data=mtf_data,
            pa_summary=pa_summary,
            structure=structure,
            fib_levels=fib_levels,
        )

