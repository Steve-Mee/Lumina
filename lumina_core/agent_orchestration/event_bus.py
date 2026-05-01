"""Central Event Bus for event-driven coordination.

The bus is intentionally small and framework-agnostic:
- thread-safe publish/subscribe
- typed event payload envelope
- bounded in-memory history per topic
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import ValidationError

from lumina_core.agent_orchestration.event_payloads import validate_event_payload

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class DomainEvent:
    topic: str
    producer: str
    payload: dict[str, Any]
    timestamp: str = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventBus:
    """Simple, central, in-process pub/sub event bus."""

    def __init__(self, *, max_topic_history: int = 500) -> None:
        self._max_topic_history = max(10, int(max_topic_history))
        self._lock = threading.RLock()
        self._callbacks: dict[str, dict[str, Callable[[DomainEvent], None]]] = defaultdict(dict)
        self._history: dict[str, deque[DomainEvent]] = defaultdict(
            lambda: deque(maxlen=self._max_topic_history)
        )
        self._seq = 0

    def publish(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> DomainEvent:
        topic_key = str(topic).strip().lower()
        if not topic_key:
            raise ValueError("topic cannot be empty")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")

        event = DomainEvent(
            topic=topic_key,
            producer=str(producer),
            payload=dict(payload),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._seq += 1
            event.metadata.setdefault("sequence", self._seq)
            self._history[topic_key].append(event)
            callbacks = list(self._callbacks.get(topic_key, {}).values())

        for callback in callbacks:
            callback(event)
        return event

    def publish_validated(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> DomainEvent | None:
        """Like ``publish`` but validates allowlisted topics; returns ``None`` on validation failure (fail-closed)."""
        topic_key = str(topic).strip().lower()
        try:
            safe_payload = validate_event_payload(topic_key, dict(payload))
        except ValidationError as exc:
            logger.warning("EventBus publish_validated rejected topic=%s: %s", topic_key, exc)
            return None
        return self.publish(
            topic=topic_key,
            producer=str(producer),
            payload=safe_payload,
            metadata=dict(metadata or {}),
        )

    def subscribe(self, topic: str, callback: Callable[[DomainEvent], None]) -> str:
        topic_key = str(topic).strip().lower()
        if not topic_key:
            raise ValueError("topic cannot be empty")
        token = f"{topic_key}:{id(callback)}:{len(self._callbacks.get(topic_key, {}))}"
        with self._lock:
            self._callbacks[topic_key][token] = callback
        return token

    def unsubscribe(self, token: str) -> None:
        with self._lock:
            for callbacks in self._callbacks.values():
                if token in callbacks:
                    del callbacks[token]
                    return

    def history(self, topic: str, *, limit: int = 100) -> list[DomainEvent]:
        topic_key = str(topic).strip().lower()
        with self._lock:
            events = list(self._history.get(topic_key, []))
        return events[-max(1, int(limit)) :]
