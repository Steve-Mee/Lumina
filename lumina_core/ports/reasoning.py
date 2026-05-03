from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReasoningPort(Protocol):
    """Contract for structured reasoning workflows."""

    def infer_json(
        self,
        payload: dict[str, Any],
        timeout: int = 20,
        context: str = "xai_json",
        max_retries: int = 1,
        decision_context_id: str | None = None,
    ) -> dict[str, Any] | None: ...
