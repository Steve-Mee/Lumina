from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExecutionPort(Protocol):
    """Contract for execution-side state mutation from decisions."""

    def apply_rl_live_decision(
        self,
        *,
        action_payload: dict[str, Any],
        current_price: float,
        regime: str,
        confidence_threshold: float,
    ) -> bool: ...

    def update_performance_log(self, performance_log: list[dict[str, Any]], trade_data: dict[str, Any]) -> None: ...
