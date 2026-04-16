from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass(slots=True)
class BlackboardEvent:
    topic: str
    producer: str
    payload: dict[str, Any]
    confidence: float
    timestamp: str
    correlation_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    sequence: int = 0
    prev_hash: str = "GENESIS"
    event_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TopicPolicy:
    critical: bool = False
    overflow_strategy: str = "drop"


DEFAULT_ALLOWED_PRODUCERS: dict[str, set[str]] = {
    "agent.rl.proposal": {"rl_policy", "test"},
    "agent.news.proposal": {"news_agent", "runtime_workers.pre_dream_daemon", "test"},
    "agent.emotional_twin.proposal": {"emotional_twin_agent", "test"},
    "agent.swarm.proposal": {"swarm_manager", "test"},
    "agent.swarm.snapshot": {"swarm_manager", "test"},
    "agent.tape.proposal": {"market_data_service", "tape_reading_agent", "test"},
    "market.tape": {"market_data_service", "tape_reading_agent", "test"},
    "execution.aggregate": {"runtime_workers.pre_dream_daemon", "runtime", "test"},
    "meta.reflection": {"meta_agent_orchestrator", "test"},
    "meta.hyperparameters": {"meta_agent_orchestrator", "test"},
    "meta.retraining": {"meta_agent_orchestrator", "test"},
    "meta.bible_update": {"meta_agent_orchestrator", "test"},
    "meta.evolution_result": {"meta_agent_orchestrator", "test"},
    "agent.meta.proposal": {"self_evolution_meta_agent", "test"},
}


DEFAULT_TOPIC_POLICIES: dict[str, TopicPolicy] = {
    "execution.aggregate": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.rl.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.news.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.emotional_twin.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.swarm.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.tape.proposal": TopicPolicy(critical=True, overflow_strategy="block_fail"),
    "agent.swarm.snapshot": TopicPolicy(critical=False, overflow_strategy="drop"),
    "market.tape": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.reflection": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.hyperparameters": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.retraining": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.bible_update": TopicPolicy(critical=False, overflow_strategy="drop"),
    "meta.evolution_result": TopicPolicy(critical=False, overflow_strategy="drop"),
    "agent.meta.proposal": TopicPolicy(critical=False, overflow_strategy="drop"),
}


class AgentBlackboard:
    """Async-capable blackboard with append-only JSONL persistence and pub/sub."""

    def __init__(
        self,
        *,
        persistence_path: Path | str = Path("state/agent_blackboard.jsonl"),
        max_topic_history: int = 500,
        obs_service: Any | None = None,
        audit_path: Path | str = Path("logs/security_audit.jsonl"),
        allowed_producers: dict[str, set[str]] | None = None,
        topic_policies: dict[str, TopicPolicy] | None = None,
    ) -> None:
        self.persistence_path = Path(persistence_path)
        self.audit_path = Path(audit_path)
        self.max_topic_history = max(10, int(max_topic_history))
        self.obs_service = obs_service
        self._lock = threading.RLock()
        self._callbacks: dict[str, dict[str, Callable[[BlackboardEvent], None]]] = defaultdict(dict)
        self._async_queues: dict[str, dict[str, asyncio.Queue[BlackboardEvent]]] = defaultdict(dict)
        self._history: dict[str, deque[BlackboardEvent]] = defaultdict(lambda: deque(maxlen=self.max_topic_history))
        self._latest: dict[str, BlackboardEvent] = {}
        self._topic_sequences: dict[str, int] = defaultdict(int)
        self._allowed_producers = dict(DEFAULT_ALLOWED_PRODUCERS)
        if allowed_producers:
            for topic, producers in allowed_producers.items():
                self._allowed_producers[str(topic).strip().lower()] = {str(item) for item in producers}
        self._topic_policies = dict(DEFAULT_TOPIC_POLICIES)
        if topic_policies:
            for topic, policy in topic_policies.items():
                self._topic_policies[str(topic).strip().lower()] = policy

        self._dual_thought_log = os.getenv("LUMINA_DUAL_THOUGHT_LOG", "true").strip().lower() == "true"
        self._thought_log_path = Path("state/thought_log.jsonl")
        self._legacy_thought_log_path = Path("state/lumina_thought_log.jsonl")

    async def publish(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        confidence: float,
        metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> BlackboardEvent:
        return self.publish_sync(
            topic=topic,
            producer=producer,
            payload=payload,
            confidence=confidence,
            metadata=metadata,
            correlation_id=correlation_id,
        )

    def publish_sync(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        confidence: float,
        metadata: dict[str, Any] | None = None,
        correlation_id: str | None = None,
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

        event = self._build_event(
            topic=topic_key,
            producer=producer,
            payload=dict(payload),
            confidence=conf,
            metadata=dict(metadata or {}),
            correlation_id=correlation_id,
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
        self._record_publish_latency(topic=topic_key, producer=producer, elapsed_ms=(time.perf_counter() - started) * 1000.0)
        return event

    def subscribe(self, topic: str, callback: Callable[[BlackboardEvent], None]) -> str:
        topic_key = str(topic).strip().lower()
        if not topic_key:
            raise ValueError("topic cannot be empty")
        token = uuid.uuid4().hex
        with self._lock:
            self._callbacks[topic_key][token] = callback
        return token

    def subscribe_async(self, topic: str, *, maxsize: int = 1000) -> tuple[str, asyncio.Queue[BlackboardEvent]]:
        topic_key = str(topic).strip().lower()
        if not topic_key:
            raise ValueError("topic cannot be empty")
        token = uuid.uuid4().hex
        queue: asyncio.Queue[BlackboardEvent] = asyncio.Queue(maxsize=max(1, int(maxsize)))
        with self._lock:
            self._async_queues[topic_key][token] = queue
        return token, queue

    def unsubscribe(self, token: str) -> None:
        with self._lock:
            for subscriptions in self._callbacks.values():
                if token in subscriptions:
                    del subscriptions[token]
                    return
            for subscriptions in self._async_queues.values():
                if token in subscriptions:
                    del subscriptions[token]
                    return

    def latest(self, topic: str) -> BlackboardEvent | None:
        topic_key = str(topic).strip().lower()
        with self._lock:
            return self._latest.get(topic_key)

    def history(self, topic: str, *, limit: int = 100, within_hours: int | None = None) -> list[BlackboardEvent]:
        topic_key = str(topic).strip().lower()
        with self._lock:
            events = list(self._history.get(topic_key, []))
        if within_hours is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=max(0, int(within_hours)))
            filtered: list[BlackboardEvent] = []
            for event in events:
                try:
                    ts = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
                except Exception:
                    continue
                if ts >= cutoff:
                    filtered.append(event)
            events = filtered
        return events[-max(1, int(limit)) :]

    def load_recent_from_disk(self, *, per_topic_limit: int = 50) -> None:
        if not self.persistence_path.exists():
            return
        topic_buckets: dict[str, deque[BlackboardEvent]] = defaultdict(lambda: deque(maxlen=max(1, int(per_topic_limit))))
        try:
            with self.persistence_path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    line = raw.strip()
                    if not line:
                        continue
                    parsed = json.loads(line)
                    event = BlackboardEvent(**parsed)
                    topic_buckets[event.topic].append(event)
        except Exception:
            return

        with self._lock:
            for topic, bucket in topic_buckets.items():
                self._history[topic] = deque(bucket, maxlen=self.max_topic_history)
                if bucket:
                    self._latest[topic] = bucket[-1]
                    self._topic_sequences[topic] = int(getattr(bucket[-1], "sequence", len(bucket)))

    def _build_event(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        confidence: float,
        metadata: dict[str, Any],
        correlation_id: str | None,
    ) -> BlackboardEvent:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            prev_hash = self._latest.get(topic).event_hash if topic in self._latest else "GENESIS"
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

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _append_thought_logs(self, event: BlackboardEvent) -> None:
        thought_payload = {
            "type": "blackboard_event",
            "topic": event.topic,
            "producer": event.producer,
            "confidence": event.confidence,
            "timestamp": event.timestamp,
            "correlation_id": event.correlation_id,
            "event_hash": event.event_hash,
            "sequence": event.sequence,
            "payload": event.payload,
        }
        self._append_jsonl(self._thought_log_path, thought_payload)
        if self._dual_thought_log:
            self._append_jsonl(self._legacy_thought_log_path, thought_payload)

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

    def _record_publish_latency(self, *, topic: str, producer: str, elapsed_ms: float) -> None:
        if self.obs_service is not None and hasattr(self.obs_service, "record_blackboard_publish"):
            try:
                self.obs_service.record_blackboard_publish(topic=topic, producer=producer, elapsed_ms=elapsed_ms)
            except Exception:
                pass

    def _record_reject(self, *, topic: str, producer: str, reason: str) -> None:
        if self.obs_service is not None and hasattr(self.obs_service, "record_blackboard_reject"):
            try:
                self.obs_service.record_blackboard_reject(topic=topic, producer=producer, reason=reason)
            except Exception:
                pass
        self._append_audit_entry(action="blackboard_reject", topic=topic, producer=producer, details={"reason": reason})

    def _record_drop(self, *, topic: str, producer: str, reason: str, critical: bool) -> None:
        if self.obs_service is not None and hasattr(self.obs_service, "record_blackboard_drop"):
            try:
                self.obs_service.record_blackboard_drop(topic=topic, producer=producer, reason=reason, critical=critical)
            except Exception:
                pass
        self._append_audit_entry(action="blackboard_drop", topic=topic, producer=producer, details={"reason": reason, "critical": critical})

    def _record_subscription_error(self, *, topic: str, producer: str, error: str) -> None:
        if self.obs_service is not None and hasattr(self.obs_service, "record_blackboard_subscription_error"):
            try:
                self.obs_service.record_blackboard_subscription_error(topic=topic, producer=producer)
            except Exception:
                pass
        self._append_audit_entry(action="blackboard_subscription_error", topic=topic, producer=producer, details={"error": error})

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
