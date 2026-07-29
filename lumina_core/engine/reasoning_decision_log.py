"""Decision-log helpers mixed into ReasoningService."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Any

from lumina_core.fault import FaultDomain, FaultPolicy
from .errors import format_error_code
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.reasoning.service")


class ReasoningDecisionLogError(RuntimeError):
    """Raised when reasoning decision logging fails in REAL mode."""


class ReasoningDecisionLogMixin:
    """Agent decision-log write path and structured logging helpers."""

    __slots__ = ()

    def _decision_log(self):
        return getattr(self.engine, "decision_log", None)

    @staticmethod
    def _safe_structured_log(logger_obj: logging.Logger, level: int, event: str, **fields: Any) -> None:
        try:
            logger_obj.log(level, event, extra={"event_data": {"event": event, **fields}})
        except Exception:
            return

    @staticmethod
    def _new_decision_context_id(context: str) -> str:
        return f"{context}:{uuid.uuid4().hex}"

    def _log_fast_rule_path(self, *, context: str, decision_context_id: str, reason: str) -> None:
        if self.llm_client is None:
            return
        self.llm_client.complete_trading_json(
            payload={"model": "fast-rule", "messages": [{"role": "system", "content": reason}], "temperature": 0.0},
            context=context,
            timeout_seconds=1,
            max_retries=0,
            decision_context_id=decision_context_id,
            forced_path="fast_rule",
            fallback_reason=reason,
        )

    def _log_decision(
        self,
        *,
        agent_id: str,
        raw_input: dict[str, Any],
        raw_output: dict[str, Any],
        confidence: float,
        policy_outcome: str,
        decision_context_id: str,
        model_version: str,
    ) -> None:
        decision_log = self._decision_log()
        if decision_log is None or not hasattr(decision_log, "log_decision"):
            return
        is_real_mode = str(getattr(self.engine.config, "trade_mode", "paper")).strip().lower() == "real"
        try:
            decision_log.log_decision(
                agent_id=agent_id,
                raw_input=raw_input,
                raw_output=raw_output,
                confidence=float(confidence),
                policy_outcome=policy_outcome,
                decision_context_id=decision_context_id,
                model_version=model_version,
                prompt_hash=hashlib.sha256(
                    json.dumps(raw_input, sort_keys=True, ensure_ascii=True).encode("utf-8")
                ).hexdigest(),
                prompt_version="reasoning-service-v1",
                policy_version="reasoning-policy-v1",
                provider_route=[str(getattr(self.inference_engine, "active_provider", "unknown-provider"))],
                calibration_factor=1.0,
                is_real_mode=is_real_mode,
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            code = format_error_code("REASONING_DECISION_LOG", exc, fallback="LOG_WRITE_FAILED")
            FaultPolicy.handle(
                domain=FaultDomain.REASONING_DECISION_LOG,
                operation="write_agent_decision_log",
                exc=exc,
                is_real_mode=is_real_mode,
                fault_cls=ReasoningDecisionLogError,
                message=f"ReasoningService failed to write agent decision log [{code}]",
                context={"agent_id": agent_id, "decision_context_id": decision_context_id},
                logger_obj=logger,
            )
            return


__all__ = ["ReasoningDecisionLogError", "ReasoningDecisionLogMixin"]
