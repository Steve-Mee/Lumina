from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .audit import AuditPort
from .dream import DreamStatePort
from .evolution import EvolutionPort
from .execution import ExecutionPort
from .market_data import MarketDataPort
from .orchestration import OrchestrationPort
from .reasoning import ReasoningPort
from .risk import RiskPort


class EngineServicePorts(BaseModel):
    """Typed service ownership map for the thin LuminaEngine orchestrator."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    risk: RiskPort
    audit: AuditPort
    orchestration: OrchestrationPort
    broker: Any
    market_data: MarketDataPort
    execution: ExecutionPort
    dream: DreamStatePort
    evolution: EvolutionPort | None = None
    reasoning: ReasoningPort | None = None
    experimental: dict[str, Any] = Field(default_factory=dict)
