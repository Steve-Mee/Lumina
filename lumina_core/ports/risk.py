from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RiskPort(Protocol):
    """Contract for risk ownership capabilities consumed by orchestrators."""

    session_guard: Any
    risk_controller: Any
    risk_policy: Any
    final_arbitration: Any
    mode_risk_profile: dict[str, float]
    dynamic_kelly_estimator: Any

    def calculate_adaptive_risk_and_qty(
        self,
        price: float,
        regime: str,
        stop_price: float,
        confidence: float | None = None,
    ) -> int: ...
