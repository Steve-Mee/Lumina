from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

ArbitrationStatus = Literal["APPROVED", "REJECTED"]


class OrderIntentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = ""


class OrderIntent(BaseModel):
    """Typed order intent contract for FinalArbitration."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    instrument: str = Field(
        min_length=1,
        max_length=32,
        validation_alias=AliasChoices("instrument", "symbol"),
        serialization_alias="instrument",
    )
    side: Literal["BUY", "SELL"]
    quantity: int = Field(gt=0)
    order_type: str = Field(default="MARKET", min_length=1, max_length=32)
    stop: float = Field(default=0.0, ge=0.0, validation_alias=AliasChoices("stop", "stop_loss"))
    target: float = Field(default=0.0, ge=0.0, validation_alias=AliasChoices("target", "take_profit"))
    reference_price: float = Field(default=0.0, ge=0.0)
    proposed_risk: float = Field(default=0.0, ge=0.0)
    regime: str = Field(default="NEUTRAL", min_length=1, max_length=32)
    confluence_score: float = Field(default=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_agent: str = Field(default="unknown", min_length=1, max_length=128)
    disable_risk_controller: bool = False
    metadata: OrderIntentMetadata = Field(default_factory=OrderIntentMetadata)


class ArbitrationState(BaseModel):
    """Typed runtime account/risk snapshot consumed by FinalArbitration."""

    model_config = ConfigDict(extra="forbid")

    runtime_mode: str = Field(default="paper", min_length=1, max_length=16)
    daily_pnl: float = 0.0
    account_equity: float = Field(default=0.0, ge=0.0)
    drawdown_pct: float = Field(default=0.0, ge=0.0)
    drawdown_kill_percent: float = Field(default=25.0, ge=0.0)
    used_margin: float = Field(default=0.0, ge=0.0)
    free_margin: float = Field(default=0.0, ge=0.0)
    margin_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    equity_snapshot_ok: bool = False
    equity_snapshot_reason: str = Field(default="not_required_non_real", min_length=1, max_length=128)
    equity_snapshot_source: str = ""
    equity_snapshot_age_sec: float = Field(default=0.0, ge=0.0)
    open_risk_by_symbol: dict[str, float] = Field(default_factory=dict)
    total_open_risk: float = Field(default=0.0, ge=0.0)
    var_95_usd: float = Field(default=0.0, ge=0.0)
    var_99_usd: float = Field(default=0.0, ge=0.0)
    es_95_usd: float = Field(default=0.0, ge=0.0)
    es_99_usd: float = Field(default=0.0, ge=0.0)
    live_position_qty: int = 0


class ArbitrationCheckStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=64)
    ok: bool
    reason: str = Field(min_length=1)


class ArbitrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ArbitrationStatus
    reason: str
    violated_principle: str | None = None
    checks: list[ArbitrationCheckStep] = Field(default_factory=list)
