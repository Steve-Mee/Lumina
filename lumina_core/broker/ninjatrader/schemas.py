"""Pydantic v2 models for NinjaTrader WebSocket frames."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NtClientInfo(_StrictModel):
    name: str
    version: str
    ninjatrader_version: str = ""


class AuthFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["auth"] = "auth"
    correlation_id: str
    ts: str
    token: str
    client: NtClientInfo


class AuthOkFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["auth_ok"] = "auth_ok"
    correlation_id: str
    ts: str
    session_id: str
    account_name: str = ""


class AuthFailedFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["auth_failed"] = "auth_failed"
    correlation_id: str
    ts: str
    code: str
    message: str


class ConnectionStatusFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["connection_status"] = "connection_status"
    correlation_id: str
    ts: str
    state: Literal["connected", "reconnecting", "disconnected", "error"]
    account_name: str = ""
    connection_name: str = ""
    ninjatrader_version: str = ""


class SubmitOrderFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["submit_order"] = "submit_order"
    correlation_id: str
    ts: str
    client_order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int = Field(ge=1)
    order_type: Literal["MARKET", "LIMIT", "STOP"] = "MARKET"
    stop_loss: float = 0.0
    take_profit: float = 0.0
    mode_context: str = "sim"


class ExecutionFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["execution"] = "execution"
    correlation_id: str
    ts: str
    execution_id: str
    order_id: str
    client_order_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: int = Field(ge=1)
    price: float
    commission: float = 0.0


class AccountSnapshotFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["account_snapshot"] = "account_snapshot"
    correlation_id: str
    ts: str
    balance: float = 0.0
    equity: float = 0.0
    available_margin: float | None = None
    realized_pnl_today: float = 0.0
    currency: str = "USD"


class PositionUpdateFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["position_update"] = "position_update"
    correlation_id: str
    ts: str
    symbol: str
    quantity: int
    avg_price: float
    side: str


class AckFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["ack"] = "ack"
    correlation_id: str
    ts: str
    ref_correlation_id: str = ""
    status: str = "ok"


class ErrorFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["error"] = "error"
    correlation_id: str
    ts: str
    code: str
    message: str
    blockers: list[dict[str, str]] = Field(default_factory=list)


class PingFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["ping"] = "ping"
    correlation_id: str
    ts: str


class PongFrame(_StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    type: Literal["pong"] = "pong"
    correlation_id: str
    ts: str


INBOUND_FRAME_TYPES: dict[str, type[_StrictModel]] = {
    "auth": AuthFrame,
    "connection_status": ConnectionStatusFrame,
    "execution": ExecutionFrame,
    "account_snapshot": AccountSnapshotFrame,
    "position_update": PositionUpdateFrame,
    "ack": AckFrame,
    "error": ErrorFrame,
    "ping": PingFrame,
}


def parse_inbound_frame(payload: dict[str, Any]) -> _StrictModel:
    frame_type = str(payload.get("type", "")).strip()
    model_cls = INBOUND_FRAME_TYPES.get(frame_type)
    if model_cls is None:
        raise ValueError(f"unknown_frame_type:{frame_type}")
    return model_cls.model_validate(payload)
