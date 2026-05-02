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
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class TradeSignal(BaseModel):
    """Contract for trade-oriented signal payloads."""

    model_config = ConfigDict(extra="allow")

    signal: str | None = None
    confidence: float | None = None
    stop: float | None = None
    target: float | None = None
    reason: str | None = None
    why_no_trade: str | None = None
    confluence_score: float | None = None
    regime: str | None = None
    hold_until_ts: float | None = None
    position_size_multiplier: float | None = Field(default=None, ge=0.0)
    min_confluence_override: float | None = None


class RiskDecision(BaseModel):
    """Contract for risk decision and gating payloads."""

    model_config = ConfigDict(extra="allow")

    approved: bool | None = None
    reason: str | None = None
    limit: str | None = None
    value: float | None = None
    risk_adjustment: float | None = None
    max_risk_percent_multiplier: float | None = Field(default=None, ge=0.0)
    rl_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class EvolutionProposal(BaseModel):
    """Contract for evolution proposals and evolution status payloads."""

    model_config = ConfigDict(extra="allow")

    status: str | None = None
    proposal: dict[str, Any] | None = None
    dna: dict[str, Any] | None = None
    generations_run: int | None = Field(default=None, ge=0)
    promotions: int | None = Field(default=None, ge=0)
    best_fitness: float | None = None
    timestamp: str | None = None


class ShadowVerdict(BaseModel):
    """Contract for shadow deployment verdict payloads."""

    model_config = ConfigDict(extra="allow")

    verdict: Literal["pass", "fail", "pending"]
    dna_hash: str | None = None
    sample_size: int | None = Field(default=None, ge=0)
    pnl: float | None = None


class ConstitutionViolation(BaseModel):
    """Contract for constitutional violation payloads."""

    model_config = ConfigDict(extra="allow")

    principle_name: str
    severity: str
    description: str | None = None
    detail: str | None = None
    mode: str | None = None


class AgentReflection(BaseModel):
    """Contract for reflective meta-agent summary payloads."""

    model_config = ConfigDict(extra="allow")

    window_hours: int | None = Field(default=None, ge=0)
    events_observed: int | None = Field(default=None, ge=0)
    avg_aggregate_confidence: float | None = None
    win_rate: float | None = None
    net_pnl: float | None = None
    sharpe: float | None = None
    reflection_confidence: float | None = None
    timestamp: str | None = None


_TOPIC_PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "trading_engine.trade_signal.emitted": TradeSignal,
    "trading_engine.dream_state.updated": TradeSignal,
    "risk.policy.decision": RiskDecision,
    "evolution.proposal.created": EvolutionProposal,
    "evolution.shadow.verdict": ShadowVerdict,
    "safety.constitution.violation": ConstitutionViolation,
    "meta.agent.reflection": AgentReflection,
}


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
        payload_model: type[BaseModel] | None = None,
    ) -> DomainEvent:
        topic_key = str(topic).strip().lower()
        if not topic_key:
            raise ValueError("topic cannot be empty")
        if not isinstance(payload, dict):
            raise TypeError("payload must be a dict")
        safe_payload = dict(payload)
        if payload_model is not None:
            safe_payload = self._validate_payload(
                topic=topic_key,
                producer=str(producer),
                payload=safe_payload,
                payload_model=payload_model,
            )

        event = DomainEvent(
            topic=topic_key,
            producer=str(producer),
            payload=safe_payload,
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

    def _validate_payload(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        payload_model: type[BaseModel],
    ) -> dict[str, Any]:
        try:
            validated = payload_model.model_validate(payload)
        except ValidationError as exc:
            logger.warning(
                "EventBus schema violation topic=%s producer=%s model=%s errors=%s",
                topic,
                producer,
                payload_model.__name__,
                exc.errors(),
            )
            raise
        return validated.model_dump(mode="json", exclude_none=False)

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
        model_cls = _TOPIC_PAYLOAD_MODELS.get(topic_key)
        try:
            return self.publish(
                topic=topic_key,
                producer=str(producer),
                payload=dict(payload),
                metadata=dict(metadata or {}),
                payload_model=model_cls,
            )
        except ValidationError as exc:
            logger.warning("EventBus publish_validated rejected topic=%s producer=%s: %s", topic_key, producer, exc)
            return None

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
