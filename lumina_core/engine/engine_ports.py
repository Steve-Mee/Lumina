from __future__ import annotations

from typing import Any, Protocol

from lumina_core.ports.audit import AuditPort
from lumina_core.ports.broker import BrokerPort
from lumina_core.ports.dream import DreamStatePort
from lumina_core.ports.evolution import EvolutionPort
from lumina_core.ports.execution import ExecutionPort
from lumina_core.ports.market_data import MarketDataPort
from lumina_core.ports.orchestration import OrchestrationPort
from lumina_core.ports.reasoning import ReasoningPort
from lumina_core.ports.risk import RiskPort


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


__all__ = [
    "AuditPort",
    "BrokerPort",
    "DreamStatePort",
    "EvolutionPort",
    "ExecutionPort",
    "MarketDataPort",
    "OrchestrationPort",
    "ReasoningPort",
    "RiskPort",
    "SupportsAnalysis",
    "SupportsDreamState",
    "SupportsExecution",
    "SupportsMarketData",
    "SupportsRisk",
]
