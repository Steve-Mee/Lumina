from datetime import date, datetime

from pydantic import BaseModel, Field


class ParticipantMetricsOut(BaseModel):
    participant_id: int
    handle: str
    pnl_total: float
    sharpe: float
    max_drawdown: float
    winrate: float


class RankingOut(BaseModel):
    rank: int
    participant_id: int
    handle: str
    score: float
    pnl_total: float
    sharpe: float
    winrate: float


class TradeReplayOut(BaseModel):
    trade_id: int
    participant_id: int
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    reflection: str
    chart_snapshot_url: str | None = None


class TradeCloseWebhookIn(BaseModel):
    participant_handle: str = Field(min_length=2, max_length=80)
    broker_name: str = Field(min_length=2, max_length=100)
    broker_account_ref: str = Field(min_length=2, max_length=140)
    account_mode: str = Field(pattern="^(paper|real)$")
    broker_fill_id: str
    symbol: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    max_drawdown_trade: float = 0.0
    reflection: str = ""
    chart_snapshot_url: str | None = None
    strategy_meta: dict | None = None


class PublicLuminaEntryIn(BaseModel):
    handle: str = Field(min_length=2, max_length=80)
    display_name: str = Field(min_length=2, max_length=120)
    api_key_plain: str = Field(min_length=16, max_length=128)
    token: str


class PublicLuminaEntryOut(BaseModel):
    participant_id: int
    handle: str
    display_name: str
    is_lumina_public: bool


class HealthOut(BaseModel):
    status: str
    service: str
    timestamp: datetime
