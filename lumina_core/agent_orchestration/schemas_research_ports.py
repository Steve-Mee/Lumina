"""Phase 5 research-side Execution Fabric ports. Additive Event Bus payloads.

These contracts align with ADR-0035 / ADR-0059. They do **not** place orders,
open a gRPC stream, or mutate NinjaTrader / live Risk Core state.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RESEARCH_SIGNAL_INTENT_TOPIC = "research.signal.intent"
RESEARCH_ORDER_INTENT_TOPIC = "research.order.intent"
RESEARCH_FILL_OBSERVED_TOPIC = "research.fill.observed"
RESEARCH_EXECUTION_ALERT_TOPIC = "research.execution.alert"

SHADOW_AGENT_ID = "research_shadow_agent"
FILL_AGENT_ID = "research_fill_agent"
SAFETY_AGENT_ID = "research_sim_safety_agent"

SIGNAL_INTENT_SCHEMA_VERSION: Literal["research.signal.intent.v1"] = "research.signal.intent.v1"
ORDER_INTENT_SCHEMA_VERSION: Literal["research.order.intent.v1"] = "research.order.intent.v1"
FILL_OBSERVED_SCHEMA_VERSION: Literal["research.fill.observed.v1"] = "research.fill.observed.v1"
EXECUTION_ALERT_SCHEMA_VERSION: Literal["research.execution.alert.v1"] = "research.execution.alert.v1"

ExecutionMode = Literal["shadow", "sim", "live"]
IntentDirection = Literal["buy", "sell"]
ExpectedHorizon = Literal["intraday", "session", "swing"]
FillSource = Literal["cost_model", "fabric"]
AlertKind = Literal["stale_data", "lost_connection", "monitor_alarm", "risk_core_limit"]
AlertAction = Literal["refuse_new_orders", "broker_protect", "deweight_reduce", "flatten_hard_limit"]

PORTS_TOPIC_PRODUCERS: dict[str, frozenset[str]] = {
    RESEARCH_SIGNAL_INTENT_TOPIC: frozenset({SHADOW_AGENT_ID}),
    RESEARCH_ORDER_INTENT_TOPIC: frozenset({SHADOW_AGENT_ID}),
    RESEARCH_FILL_OBSERVED_TOPIC: frozenset({FILL_AGENT_ID, SHADOW_AGENT_ID}),
    RESEARCH_EXECUTION_ALERT_TOPIC: frozenset({SAFETY_AGENT_ID}),
}

PORTS_GUARDED_TOPICS: frozenset[str] = frozenset(PORTS_TOPIC_PRODUCERS)


class SignalIntent(BaseModel):
    """Research-layer signal. Maps later to Fabric; Phase 5 only logs it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.signal.intent.v1"] = SIGNAL_INTENT_SCHEMA_VERSION
    strategy_id: str = Field(min_length=1)
    direction: IntentDirection
    size: float = Field(gt=0.0)
    timestamp: str = Field(min_length=1)
    expected_horizon: ExpectedHorizon
    instrument: Literal["ES", "NQ", "MES", "MNQ"]
    account_id: str = Field(min_length=1)
    mode: ExecutionMode
    client_order_id: str = Field(min_length=1)
    provenance_mac: str = Field(min_length=64, max_length=64)


class ResearchOrderIntent(BaseModel):
    """Research-layer OrderIntent shape. Not ``lumina_core.risk.schemas.OrderIntent``."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.order.intent.v1"] = ORDER_INTENT_SCHEMA_VERSION
    strategy_id: str = Field(min_length=1)
    direction: IntentDirection
    size: float = Field(gt=0.0)
    timestamp: str = Field(min_length=1)
    expected_horizon: ExpectedHorizon
    instrument: Literal["ES", "NQ", "MES", "MNQ"]
    account_id: str = Field(min_length=1)
    mode: ExecutionMode
    client_order_id: str = Field(min_length=1)
    order_type: Literal["MARKET", "LIMIT"] = "LIMIT"
    limit_price: float | None = Field(default=None, gt=0.0)
    provenance_mac: str = Field(min_length=64, max_length=64)


class ResearchFillEvent(BaseModel):
    """Fill SSOT for decay monitoring and cost calibration. Fabric fills are typed, not wired."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.fill.observed.v1"] = FILL_OBSERVED_SCHEMA_VERSION
    strategy_id: str = Field(min_length=1)
    fill_price: float = Field(gt=0.0)
    qty: float = Field(gt=0.0)
    slippage: float
    commission: float
    timestamp: str = Field(min_length=1)
    fill_id: str = Field(min_length=1)
    instrument: Literal["ES", "NQ", "MES", "MNQ"]
    client_order_id: str = Field(min_length=1)
    source: FillSource
    provenance_mac: str = Field(min_length=64, max_length=64)


class ExecutionAlert(BaseModel):
    """Fail-closed execution alert. Never increases exposure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research.execution.alert.v1"] = EXECUTION_ALERT_SCHEMA_VERSION
    alert_id: str = Field(min_length=1)
    kind: AlertKind
    action: AlertAction
    allow_new_orders: bool
    flatten_recommended: bool
    open_position: bool
    reason: str = Field(min_length=1)
    provenance_mac: str = Field(min_length=64, max_length=64)
