from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable


@runtime_checkable
class OrchestrationPort(Protocol):
    """Contract for event-driven orchestration facilities."""

    def publish(
        self,
        *,
        topic: str,
        producer: str,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        payload_model: type[Any] | None = None,
    ) -> Any: ...

    def subscribe(self, topic: str, callback: Callable[[Any], None]) -> str: ...
