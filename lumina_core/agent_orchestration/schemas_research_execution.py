"""Additive Event Bus contracts for research SHADOW execution (S0).

Existing ``TradeIntent`` / live ``OrderIntent`` stay unchanged. Research
SHADOW uses these additive topics, not Final Arbitration. Issuer-guarded:
only ``research_bridge`` may publish them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RESEARCH_EXECUTION_SIGNAL_TOPIC = "research.execution.signal_intent"
RESEARCH_EXECUTION_ORDER_TOPIC = "research.execution.order_intent"
RESEARCH_EXECUTION_FILL_TOPIC = "research.execution.fill"

RESEARCH_BRIDGE_AGENT_ID = "research_bridge"
FILL_TRANSLATOR_AGENT_ID = "fill_translator"

SIGNAL_INTENT_SCHEMA_VERSION: Literal["research.execution.signal_intent.v1"] = (
    "research.execution.signal_intent.v1"
)
ORDER_INTENT_SCHEMA_VERSION: Literal["research.execution.order_intent.v1"] = (
    "research.execution.order_intent.v1"
)
FILL_SCHEMA_VERSION: Literal["research.execution.fill.v1"] = "research.execution.fill.v1"

RESEARCH_EXECUTION_TOPIC_PRODUCERS: dict[str, frozenset[str]] = {
    RESEARCH_EXECUTION_SIGNAL_TOPIC: frozenset({RESEARCH_BRIDGE_AGENT_ID}),
    RESEARCH_EXECUTION_ORDER_TOPIC: frozenset({RESEARCH_BRIDGE_AGENT_ID}),
    RESEARCH_EXECUTION_FILL_TOPIC: frozenset({RESEARCH_BRIDGE_AGENT_ID, FILL_TRANSLATOR_AGENT_ID}),
}

RESEARCH_EXECUTION_GUARDED_TOPICS: frozenset[str] = frozenset(
    {
        RESEARCH_EXECUTION_SIGNAL_TOPIC,
        RESEARCH_EXECUTION_ORDER_TOPIC,
        RESEARCH_EXECUTION_FILL_TOPIC,
    }
)

InstrumentRoot = Literal["ES", "NQ", "MES", "MNQ"]
Direction = Literal["BUY", "SELL"]
FillSource = Literal["broker", "hypothetical_adr0055"]


class SignalIntent(BaseModel):
    """Logged research signal. S0 never admits this to the broker."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.execution.signal_intent.v1"] = SIGNAL_INTENT_SCHEMA_VERSION
    strategy_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    instrument: InstrumentRoot
    direction: Direction
    size: float = Field(gt=0.0)
    timestamp: datetime
    expected_horizon: int = Field(ge=1)
    validation_mac: str = Field(min_length=64, max_length=64)
    issue_mac: str = Field(min_length=64, max_length=64)
    source: Literal["research_bridge"] = RESEARCH_BRIDGE_AGENT_ID


class ResearchExecutionOrderIntent(BaseModel):
    """S0: logged, never admitted. ``admitted`` is frozen False."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.execution.order_intent.v1"] = ORDER_INTENT_SCHEMA_VERSION
    strategy_id: str = Field(min_length=1)
    config_id: str = Field(min_length=1)
    trial_id: int = Field(ge=1)
    instrument: InstrumentRoot
    direction: Direction
    size: float = Field(gt=0.0)
    timestamp: datetime
    expected_horizon: int = Field(ge=1)
    validation_mac: str = Field(min_length=64, max_length=64)
    issue_mac: str = Field(min_length=64, max_length=64)
    source: Literal["research_bridge"] = RESEARCH_BRIDGE_AGENT_ID
    admitted: Literal[False] = False


class ResearchExecutionFill(BaseModel):
    """Hypothetical or broker fill on the research execution topic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.execution.fill.v1"] = FILL_SCHEMA_VERSION
    fill_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    side: Direction
    quantity: int = Field(gt=0)
    price: float
    commission: float
    event_ts: datetime
    slippage_ticks: float = 0.0
    slippage_usd: float = 0.0
    commission_ticks: float = 0.0
    source: FillSource
    strategy_id: str = Field(min_length=1)
    expected_horizon: int = Field(ge=1)

    @property
    def fill_price(self) -> float:
        return self.price

    @property
    def qty(self) -> int:
        return self.quantity


def guard_research_execution(producer: str, _payload: dict[str, object]) -> bool:
    """Issuer guard for signal/order topics: only ``research_bridge``."""
    return str(producer).strip() == RESEARCH_BRIDGE_AGENT_ID


def guard_research_execution_fill(producer: str, _payload: dict[str, object]) -> bool:
    """Issuer guard for fill topic: research_bridge (S2: also fill_translator)."""
    return str(producer).strip() in {RESEARCH_BRIDGE_AGENT_ID, FILL_TRANSLATOR_AGENT_ID}
