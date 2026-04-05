from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class TradeSubmit(BaseModel):
    participant: str
    mode: str
    symbol: str
    signal: str
    entry: float
    exit: float
    qty: float
    pnl: float
    broker_fill_id: str | None = None
    commission: float | None = None
    slippage_points: float | None = None
    fill_latency_ms: float | None = None
    reconciliation_status: str | None = None
    reflection: dict[str, Any] = Field(default_factory=dict)
    chart_base64: str | None = None


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    participant: str
    mode: str
    ts: datetime
    symbol: str
    signal: str
    entry: float
    exit: float
    qty: float
    pnl: float
    broker_fill_id: str | None = None
    commission: float | None = None
    slippage_points: float | None = None
    fill_latency_ms: float | None = None
    reconciliation_status: str | None = None
    sharpe: float
    maxdd: float
    reflection: dict[str, Any]
    chart_base64: str | None = None


class LeaderboardRow(BaseModel):
    participant: str
    mode: str
    trades: int
    total_pnl: float
    avg_pnl: float
    sharpe: float
    maxdd: float


class BibleUpload(BaseModel):
    trader_name: str
    evolvable_layer: Dict[str, Any]
    backtest_results: Dict[str, Any]


class ReflectionUpload(BaseModel):
    trader_name: str
    reflection: str
    key_lesson: str
    suggested_update: Dict[str, Any]
    pnl_impact: float | None = None
