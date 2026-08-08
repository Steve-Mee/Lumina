"""Blackboard publish + proposal + event build (M5)."""
from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from lumina_core.agent_orchestration.schemas import (
    BLACKBOARD_TOPIC_MODELS,
    model_validate_payload_with_instance,
)
from lumina_core.engine.agent_blackboard_types import BlackboardEvent, TopicPolicy
from lumina_core.state.state_manager import safe_append_jsonl

logger = logging.getLogger(__name__)


class AgentBlackboardPublishMixin:
    def publish_sync(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        confidence: float,
        metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
        payload_model: type[BaseModel] | None = None,
    ) -> BlackboardEvent:
        started = time.perf_counter()
        topic_key = str(topic).strip().lower()
        if not topic_key:
            self._record_reject(topic="<empty>", producer=producer, reason="empty_topic")
            raise ValueError("topic cannot be empty")
        conf = float(confidence)
        if conf < 0.0 or conf > 1.0:
            self._record_reject(topic=topic_key, producer=producer, reason="invalid_confidence")
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not isinstance(payload, dict):
            self._record_reject(topic=topic_key, producer=producer, reason="payload_not_dict")
            raise TypeError("payload must be a dict")
        self._validate_producer(topic=topic_key, producer=producer)
        safe_payload = dict(payload)
        payload_instance: BaseModel | None = None
        selected_payload_model = payload_model or BLACKBOARD_TOPIC_MODELS.get(topic_key)
        if selected_payload_model is not None:
            try:
                safe_payload, payload_instance = model_validate_payload_with_instance(
                    payload=safe_payload,
                    payload_model=selected_payload_model,
                )
            except ValidationError as exc:
                self._record_reject(topic=topic_key, producer=producer, reason="schema_violation")
                logger.warning(
                    "AgentBlackboard schema violation topic=%s producer=%s model=%s errors=%s",
                    topic_key,
                    producer,
                    selected_payload_model.__name__,
                    exc.errors(),
                )
                raise

        event = self._build_event(
            topic=topic_key,
            producer=producer,
            payload=safe_payload,
            confidence=conf,
            metadata=dict(metadata or {}),
            correlation_id=correlation_id,
            payload_instance=payload_instance,
        )
        with self._lock:
            self._history[topic_key].append(event)
            self._latest[topic_key] = event
            self._append_jsonl(self.persistence_path, event.to_dict())
            self._append_thought_logs(event)

            callbacks = list(self._callbacks.get(topic_key, {}).values())
            async_queues = list(self._async_queues.get(topic_key, {}).values())

        for callback in callbacks:
            try:
                callback(event)
            except Exception as exc:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/agent_blackboard.py:225")
                self._record_subscription_error(topic=topic_key, producer=producer, error=str(exc))
                continue

        for queue in async_queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                policy = self._policy_for_topic(topic_key)
                self._record_drop(topic=topic_key, producer=producer, reason="queue_full", critical=policy.critical)
                if policy.critical or str(policy.overflow_strategy).strip().lower() == "block_fail":
                    raise RuntimeError(f"critical blackboard topic queue full: {topic_key}")
                continue
        self._record_publish_latency(
            topic=topic_key, producer=producer, elapsed_ms=(time.perf_counter() - started) * 1000.0
        )
        return event

    def add_proposal(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        confidence: float,
        metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> BlackboardEvent:
        topic_key = str(topic).strip().lower()
        if not topic_key.startswith("agent.") or not topic_key.endswith(".proposal"):
            raise ValueError("add_proposal requires an agent.*.proposal topic")

        # Phase 2 Slice 12 (defensive upstream threading): If the engine carries an active
        # cycle-level decision_context_id from dream/multi-agent coordination (see pre_dream_daemon),
        # honor it when the immediate caller did not supply a correlation_id. This lets future
        # agents inside a marked cycle participate in the shared lineage root without every call site
        # being updated in this slice. Non-breaking; only a read of an optional engine attribute.
        if correlation_id is None:
            try:
                eng = getattr(self, "engine", None)
                if eng is not None:
                    active = getattr(eng, "_active_decision_context_id", None) or getattr(eng, "active_decision_context_id", None)
                    if active:
                        correlation_id = str(active)
            except Exception:
                pass

        # Phase 2 Slice 08: Ensure decision_context_id (upstream lineage root) is present for proposals.
        # We align it with correlation_id so the lineage thread is consistent.
        if correlation_id is None:
            correlation_id = uuid.uuid4().hex
        safe_payload = dict(payload)
        safe_payload.setdefault("decision_context_id", correlation_id)

        blackboard_event = self.publish_sync(
            topic=topic_key,
            producer=producer,
            payload=safe_payload,
            confidence=confidence,
            metadata=metadata,
            correlation_id=correlation_id,
        )

        # Phase 2 Slice 10: Also publish to the main Event Bus as a first-class typed event
        # (in addition to blackboard) so the central spine has unified proposal lineage.
        try:
            engine = getattr(self, "engine", None)
            event_bus = getattr(engine, "event_bus", None) if engine else None
            if event_bus and hasattr(event_bus, "publish_validated"):
                main_bus_event = event_bus.publish_validated(
                    topic=topic_key,
                    producer=producer,
                    payload=safe_payload,
                    metadata=metadata or {},
                )
                # Phase 2 Slice 11: Attach proper event_hash so deeper prev_hash chaining can start from this proposal event on the main bus.
                if main_bus_event:
                    try:
                        from lumina_core.order_gatekeeper import _domain_event_fingerprint
                        main_bus_event.metadata["event_hash"] = _domain_event_fingerprint(main_bus_event)
                    except Exception:
                        pass
        except Exception:
            pass  # Best-effort dual publish only

        return blackboard_event

    def mark_policy_decision(self, *, approved: bool, reason: str = "") -> None:
        with self._lock:
            self._last_policy_approval = bool(approved)
            self._last_policy_decision_ts = time.time()
            self._last_policy_reason = str(reason or "")

    def is_proposal_approved_by_policy(self) -> bool:
        with self._lock:
            return bool(self._last_policy_approval)

    def _build_event(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        confidence: float,
        metadata: dict[str, Any],
        correlation_id: str | None,
        payload_instance: BaseModel | None = None,
    ) -> BlackboardEvent:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            prev_hash = self._latest[topic].event_hash if topic in self._latest else "GENESIS"
            self._topic_sequences[topic] += 1
            sequence = self._topic_sequences[topic]
        event = BlackboardEvent(
            topic=topic,
            producer=str(producer),
            payload=payload,
            confidence=confidence,
            timestamp=now,
            correlation_id=str(correlation_id or uuid.uuid4().hex),
            metadata=metadata,
            sequence=sequence,
            prev_hash=prev_hash,
            payload_instance=payload_instance,
        )
        canonical = json.dumps(
            {
                "topic": event.topic,
                "producer": event.producer,
                "payload": event.payload,
                "confidence": event.confidence,
                "timestamp": event.timestamp,
                "correlation_id": event.correlation_id,
                "metadata": event.metadata,
                "sequence": event.sequence,
                "prev_hash": event.prev_hash,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        event.event_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return event

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        safe_append_jsonl(path, payload, hash_chain=False)

    def _append_thought_logs(self, event: BlackboardEvent) -> None:
        export = event.to_dict()
        thought_payload = {
            "type": "blackboard_event",
            "topic": event.topic,
            "producer": event.producer,
            "confidence": event.confidence,
            "timestamp": event.timestamp,
            "correlation_id": event.correlation_id,
            "event_hash": event.event_hash,
            "sequence": event.sequence,
            "payload": export.get("payload", event.payload),
        }
        if "payload_model" in export:
            thought_payload["payload_model"] = export["payload_model"]
        self._append_jsonl(self._thought_log_path, thought_payload)

    def _policy_for_topic(self, topic: str) -> TopicPolicy:
        return self._topic_policies.get(str(topic).strip().lower(), TopicPolicy())

    def _validate_producer(self, *, topic: str, producer: str) -> None:
        allowed = self._allowed_producers.get(topic)
        if allowed is None:
            return
        normalized = str(producer).strip()
        if normalized in allowed:
            return
        self._record_reject(topic=topic, producer=producer, reason="unauthorized_producer")
        raise PermissionError(f"producer '{producer}' is not allowed on topic '{topic}'")

