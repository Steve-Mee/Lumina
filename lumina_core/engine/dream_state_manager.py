from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from .dream_state import DreamState
from .engine_ports import SupportsDreamState

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DreamStateManager:
    """Encapsulates dream-state read/write and event publication."""

    engine: SupportsDreamState
    dream_state: DreamState

    def snapshot(self) -> dict[str, Any]:
        return self.dream_state.snapshot()

    def set_fields(self, updates: dict[str, Any]) -> None:
        self.dream_state.update(updates)
        event_bus = getattr(self.engine, "event_bus", None)
        if event_bus is not None and hasattr(event_bus, "publish_validated"):
            try:
                event_bus.publish_validated(
                    topic="trading_engine.dream_state.updated",
                    producer="lumina_engine",
                    payload=dict(updates),
                )
            except Exception:
                logger.exception("DreamStateManager failed to publish dream_state update event")

    def set_value(self, key: str, value: Any) -> None:
        self.dream_state.set_value(key, value)
