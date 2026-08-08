"""Blackboard metrics + audit (M5)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.state.state_manager import safe_append_jsonl

logger = logging.getLogger(__name__)


class AgentBlackboardMetricsMixin:
    def _record_publish_latency(self, *, topic: str, producer: str, elapsed_ms: float) -> None:
        if self.obs_service is not None and hasattr(self.obs_service, "record_blackboard_publish"):
            try:
                self.obs_service.record_blackboard_publish(topic=topic, producer=producer, elapsed_ms=elapsed_ms)
            except Exception:
                logger.exception("AgentBlackboard failed to record publish latency")

    def _record_reject(self, *, topic: str, producer: str, reason: str) -> None:
        if self.obs_service is not None and hasattr(self.obs_service, "record_blackboard_reject"):
            try:
                self.obs_service.record_blackboard_reject(topic=topic, producer=producer, reason=reason)
            except Exception:
                logger.exception("AgentBlackboard failed to record reject metric")
        self._append_audit_entry(action="blackboard_reject", topic=topic, producer=producer, details={"reason": reason})

    def _record_drop(self, *, topic: str, producer: str, reason: str, critical: bool) -> None:
        if self.obs_service is not None and hasattr(self.obs_service, "record_blackboard_drop"):
            try:
                self.obs_service.record_blackboard_drop(
                    topic=topic, producer=producer, reason=reason, critical=critical
                )
            except Exception:
                logger.exception("AgentBlackboard failed to record drop metric")
        self._append_audit_entry(
            action="blackboard_drop", topic=topic, producer=producer, details={"reason": reason, "critical": critical}
        )

    def _record_subscription_error(self, *, topic: str, producer: str, error: str) -> None:
        if self.obs_service is not None and hasattr(self.obs_service, "record_blackboard_subscription_error"):
            try:
                self.obs_service.record_blackboard_subscription_error(topic=topic, producer=producer)
            except Exception:
                logger.exception("AgentBlackboard failed to record subscription error metric")
        self._append_audit_entry(
            action="blackboard_subscription_error", topic=topic, producer=producer, details={"error": error}
        )

    def _append_audit_entry(self, *, action: str, topic: str, producer: str, details: dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "user_id": "system",
            "username": str(producer),
            "resource": str(topic),
            "status": "recorded",
            "details": details,
        }
        self._append_jsonl(self.audit_path, payload)
