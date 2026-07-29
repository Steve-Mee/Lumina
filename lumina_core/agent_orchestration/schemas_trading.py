"""Typed EventBus / Blackboard payload contracts (trading).

Canonical re-export surface: ``lumina_core.agent_orchestration.schemas``.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class TradeIntent(BaseModel):
    """Contract for trade-oriented signal payloads."""

    model_config = ConfigDict(extra="forbid")

    signal: str | None = None
    confidence: float | None = None
    stop: float | None = None
    target: float | None = None
    reason: str | None = None
    why_no_trade: str | None = None
    confluence_score: float | None = None
    regime: str | None = None
    hold_until_ts: float | None = None
    position_size_multiplier: float | None = Field(default=None, ge=0.0)
    min_confluence_override: float | None = None


TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC = "trading_engine.execution.aggregate"


class TradingEngineExecutionAggregate(BaseModel):
    """Strict EventBus contract for pre-trade execution consensus snapshots.

    Published only via EventBus (canonical). Unknown top-level keys are rejected;
    callers should pass payloads already filtered to known fields or use
    ``filter_payload_for_execution_aggregate``.
    """

    model_config = ConfigDict(extra="forbid")

    signal: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    confluence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    stop: float | None = None
    target: float | None = None
    reason: str | None = None
    why_no_trade: str | None = None
    chosen_strategy: str | None = None
    narrative_reasoning: str | None = None
    fib_levels_drawn: dict[str, Any] | None = None
    executed: bool | None = None
    pnl: float | None = None
    approved: bool | None = None
    hold_until_ts: float | None = None
    regime: str | None = None
    expected_value: float | None = None
    position_size_multiplier: float | None = Field(default=None, ge=0.0)


# Phase 2 Slice 18: First-class typed fill event with full lineage
EXECUTION_FILL_RECEIVED_TOPIC = "execution.fill.received"


class ExecutionFill(BaseModel):
    """Typed Event Bus contract for actual fills received from the broker.

    This is the downstream counterpart to the pre-trade lineage.
    Carries decision_context_id + prev_hash so the cryptographic chain
    continues from Final Arbitration / submission into real execution.

    Published best-effort via publish_validated when a fill is created
    or ingested (paper and live paths).
    """

    model_config = ConfigDict(extra="forbid")

    # Lineage (the important part for Phase 2)
    decision_context_id: str | None = None
    prev_hash: str | None = None
    prev_event_topic: str | None = None

    # Core fill data
    fill_id: str
    order_id: str | None = None
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: str
    commission: float = 0.0

    # Optional raw passthrough for broker-specific details
    raw: dict[str, Any] = Field(default_factory=dict)
    min_confluence: float | None = None
    meta_score: float | None = None
    agent_id: str | None = None
    sentiment_signal: str | None = None


def filter_payload_for_execution_aggregate(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop unknown keys so LLM/dream JSON can be validated against strict aggregate schema."""
    allowed = TradingEngineExecutionAggregate.model_fields.keys()
    return {k: v for k, v in payload.items() if k in allowed}

class DreamStateEventPayload(TradeIntent):
    """Experimental dream-state payload envelope.

    This topic intentionally remains extensible while dream-state fields are
    being stabilized and gradually migrated into explicit schema fields.
    """

    model_config = ConfigDict(extra="allow")


DreamState = DreamStateEventPayload

class ExecutionAggregatePayload(BaseModel):
    """Contract for execution aggregate topic payloads."""

    model_config = ConfigDict(extra="allow")

    signal: str | None = None
    executed: bool | None = None
    pnl: float | None = None
    approved: bool | None = None
    reason: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MarketTapePayload(BaseModel):
    """Contract for market tape snapshots."""

    model_config = ConfigDict(extra="allow")

    symbol: str | None = None
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = Field(default=None, ge=0.0)
    signal: str | None = None

