from __future__ import annotations

from typing import Any, Protocol


class SupportsMarketData(Protocol):
    market_data: Any
    config: Any


class SupportsAnalysis(Protocol):
    config: Any
    regime_detector: Any
    current_regime_snapshot: dict[str, Any]
    cost_tracker: dict[str, Any]

    def get_current_dream_snapshot(self) -> dict[str, Any]: ...


class SupportsRisk(Protocol):
    config: Any
    account_equity: float
    valuation_engine: Any
    app: Any


class SupportsDreamState(Protocol):
    event_bus: Any


class SupportsExecution(Protocol):
    blackboard: Any

    def set_current_dream_fields(self, updates: dict[str, Any]) -> None: ...
