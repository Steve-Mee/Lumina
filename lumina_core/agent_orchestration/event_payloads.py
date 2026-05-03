"""Compatibility facade for EventBus payload validation.

Use ``lumina_core.agent_orchestration.schemas`` as the canonical source of
typed topic contracts. This module remains for backward-compatible imports.
"""

from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.schemas import (
    registered_event_topics,
    validate_registered_event_payload,
)

__all__ = ["validate_event_payload", "registered_typed_topics"]


def validate_event_payload(topic: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-roundtrippable dict for ``topic``, or raise ``ValidationError``."""
    return validate_registered_event_payload(topic=topic, payload=payload)


def registered_typed_topics() -> frozenset[str]:
    return registered_event_topics()
