"""Pydantic payload contracts for selected EventBus topics (allowlist).

Unknown topics are passed through unchanged by ``validate_event_payload``.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class DreamStateUpdatedPayload(BaseModel):
    """Subset validation for ``trading_engine.dream_state.updated`` partial updates."""

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


_TOPIC_MODELS: dict[str, type[BaseModel]] = {
    "trading_engine.dream_state.updated": DreamStateUpdatedPayload,
}


def validate_event_payload(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-roundtrippable dict for ``topic``, or raise ``ValidationError``."""
    key = str(topic).strip().lower()
    model_cls = _TOPIC_MODELS.get(key)
    if model_cls is None:
        return dict(payload)
    validated = model_cls.model_validate(payload)
    return validated.model_dump(mode="json", exclude_none=False)


def registered_typed_topics() -> frozenset[str]:
    return frozenset(_TOPIC_MODELS.keys())
