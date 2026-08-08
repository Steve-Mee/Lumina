"""AgentBlackboard — typed in-process topic bus (M5 façade)."""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel

from lumina_core.engine.agent_blackboard_metrics import AgentBlackboardMetricsMixin
from lumina_core.engine.agent_blackboard_publish import AgentBlackboardPublishMixin
from lumina_core.engine.agent_blackboard_types import (
    DEFAULT_ALLOWED_PRODUCERS,
    DEFAULT_TOPIC_POLICIES,
    BlackboardEvent,
    TopicPolicy,
)

logger = logging.getLogger(__name__)


class AgentBlackboard(
    AgentBlackboardPublishMixin,
    AgentBlackboardMetricsMixin,
):
    """Async-capable blackboard with append-only JSONL persistence and pub/sub."""

    @staticmethod
    def _default_persistence_path() -> Path:
        """Return default persistence path, honouring LUMINA_STATE_DIR env var."""
        state_dir = os.getenv("LUMINA_STATE_DIR", "state")
        return Path(state_dir) / "agent_blackboard.jsonl"

    @staticmethod
    def _default_audit_path() -> Path:
        """Return default audit path, honouring LUMINA_LOGS_DIR env var."""
        logs_dir = os.getenv("LUMINA_LOGS_DIR", "logs")
        return Path(logs_dir) / "security_audit.jsonl"

    def __init__(
        self,
        *,
        persistence_path: Path | str | None = None,
        max_topic_history: int = 500,
        obs_service: Any | None = None,
        audit_path: Path | str | None = None,
        allowed_producers: dict[str, set[str]] | None = None,
        topic_policies: dict[str, TopicPolicy] | None = None,
    ) -> None:
        self.persistence_path = (
            Path(persistence_path) if persistence_path is not None else self._default_persistence_path()
        )
        self.audit_path = Path(audit_path) if audit_path is not None else self._default_audit_path()
        self.max_topic_history = max(10, int(max_topic_history))
        self.obs_service = obs_service
        self._lock = threading.RLock()
        self._callbacks: dict[str, dict[str, Callable[[BlackboardEvent], None]]] = defaultdict(dict)
        self._async_queues: dict[str, dict[str, asyncio.Queue[BlackboardEvent]]] = defaultdict(dict)
        self._history: dict[str, deque[BlackboardEvent]] = defaultdict(lambda: deque(maxlen=self.max_topic_history))
        self._latest: dict[str, BlackboardEvent] = {}
        self._topic_sequences: dict[str, int] = defaultdict(int)
        self._last_policy_approval: bool = False
        self._last_policy_decision_ts: float = 0.0
        self._last_policy_reason: str = ""
        self._allowed_producers = dict(DEFAULT_ALLOWED_PRODUCERS)
        if allowed_producers:
            for topic, producers in allowed_producers.items():
                self._allowed_producers[str(topic).strip().lower()] = {str(item) for item in producers}
        self._topic_policies = dict(DEFAULT_TOPIC_POLICIES)
        if topic_policies:
            for topic, policy in topic_policies.items():
                self._topic_policies[str(topic).strip().lower()] = policy

        # Respect LUMINA_STATE_DIR for test isolation (set in conftest.py).
        _state_dir = Path(os.getenv("LUMINA_STATE_DIR", "state"))
        self._thought_log_path = _state_dir / "thought_log.jsonl"

    async def publish(
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
        return self.publish_sync(
            topic=topic,
            producer=producer,
            payload=payload,
            confidence=confidence,
            metadata=metadata,
            correlation_id=correlation_id,
            payload_model=payload_model,
        )

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
                    logging.exception(
                        "Unhandled broad exception fallback in lumina_core/engine/agent_blackboard.py:326"
                    )
                    continue
                if ts >= cutoff:
                    filtered.append(event)
            events = filtered
        return events[-max(1, int(limit)) :]

    def load_recent_from_disk(self, *, per_topic_limit: int = 50) -> None:
        if not self.persistence_path.exists():
            return
        topic_buckets: dict[str, deque[BlackboardEvent]] = defaultdict(
            lambda: deque(maxlen=max(1, int(per_topic_limit)))
        )
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
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/agent_blackboard.py:348")
            return

        with self._lock:
            for topic, bucket in topic_buckets.items():
                self._history[topic] = deque(bucket, maxlen=self.max_topic_history)
                if bucket:
                    self._latest[topic] = bucket[-1]
                    self._topic_sequences[topic] = int(getattr(bucket[-1], "sequence", len(bucket)))



__all__ = [
    "AgentBlackboard",
    "BlackboardEvent",
    "TopicPolicy",
    "DEFAULT_ALLOWED_PRODUCERS",
    "DEFAULT_TOPIC_POLICIES",
]
