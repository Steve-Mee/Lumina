"""Map between broker domain types and Execution Fabric protobuf messages."""

from __future__ import annotations

import time
import uuid
from typing import Any

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Order, Position

try:
    from lumina_core.broker.ninjatrader.generated import fabric_pb2
except ImportError as exc:  # pragma: no cover - stubs must be generated for runtime
    raise ImportError(
        "Fabric stubs missing. Run: python scripts/generate_fabric_proto.py"
    ) from exc


def _now_ms() -> int:
    return int(time.time() * 1000)


def map_order_action(side: str) -> int:
    text = str(side or "").strip().upper()
    if text in {"BUY", "LONG", "B"}:
        return fabric_pb2.ORDER_ACTION_BUY
    if text in {"SELL", "SHORT", "S"}:
        return fabric_pb2.ORDER_ACTION_SELL
    return fabric_pb2.ORDER_ACTION_UNSPECIFIED


def map_order_type(order_type: str) -> int:
    text = str(order_type or "MARKET").strip().upper()
    if text == "MARKET":
        return fabric_pb2.ORDER_TYPE_MARKET
    if text == "LIMIT":
        return fabric_pb2.ORDER_TYPE_LIMIT
    if text == "STOP":
        return fabric_pb2.ORDER_TYPE_STOP
    if text in {"STOP_LIMIT", "STOPLIMIT"}:
        return fabric_pb2.ORDER_TYPE_STOP_LIMIT
    return fabric_pb2.ORDER_TYPE_UNSPECIFIED


def order_action_to_side(action: int) -> str:
    if action == fabric_pb2.ORDER_ACTION_BUY:
        return "BUY"
    if action == fabric_pb2.ORDER_ACTION_SELL:
        return "SELL"
    return "UNKNOWN"


def order_to_place_command(
    order: Order,
    *,
    client_order_id: str,
    correlation_id: str,
    mode_context: str = "sim",
    reduce_only: bool = False,
    protected: bool = False,
) -> fabric_pb2.PlaceOrderCommand:
    meta = order.metadata if isinstance(order.metadata, dict) else {}
    price = 0.0
    stop_price = float(order.stop_loss or 0.0)
    if meta.get("price") is not None:
        price = float(meta["price"])  # type: ignore[arg-type]
    if meta.get("stop_price") is not None:
        stop_price = float(meta["stop_price"])  # type: ignore[arg-type]
    if meta.get("reduce_only") is not None:
        reduce_only = bool(meta["reduce_only"])
    if meta.get("protected") is not None:
        protected = bool(meta["protected"])

    return fabric_pb2.PlaceOrderCommand(
        client_order_id=client_order_id,
        instrument=str(order.symbol),
        action=map_order_action(order.side),
        quantity=max(1, int(order.quantity)),
        order_type=map_order_type(order.order_type),
        price=price,
        stop_price=stop_price,
        time_in_force=fabric_pb2.TIME_IN_FORCE_DAY,
        reduce_only=reduce_only,
        protected=protected,
        correlation_id=correlation_id,
        mode_context=str(mode_context or "sim"),
    )


def place_command_to_brain_message(cmd: fabric_pb2.PlaceOrderCommand) -> fabric_pb2.BrainMessage:
    return fabric_pb2.BrainMessage(place_order=cmd)


def flatten_to_brain_message(*, instrument: str = "", correlation_id: str = "", emergency: bool = False) -> fabric_pb2.BrainMessage:
    return fabric_pb2.BrainMessage(
        flatten=fabric_pb2.FlattenCommand(
            instrument=str(instrument or ""),
            correlation_id=correlation_id or str(uuid.uuid4()),
            emergency=bool(emergency),
        )
    )


def cancel_to_brain_message(
    *,
    client_order_id: str = "",
    nt_order_id: str = "",
    correlation_id: str = "",
) -> fabric_pb2.BrainMessage:
    return fabric_pb2.BrainMessage(
        cancel_order=fabric_pb2.CancelOrderCommand(
            client_order_id=str(client_order_id or ""),
            nt_order_id=str(nt_order_id or ""),
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
    )


def modify_to_brain_message(
    *,
    client_order_id: str = "",
    nt_order_id: str = "",
    quantity: int = 0,
    price: float = 0.0,
    stop_price: float = 0.0,
    correlation_id: str = "",
) -> fabric_pb2.BrainMessage:
    return fabric_pb2.BrainMessage(
        modify_order=fabric_pb2.ModifyOrderCommand(
            client_order_id=str(client_order_id or ""),
            nt_order_id=str(nt_order_id or ""),
            quantity=int(quantity or 0),
            price=float(price or 0.0),
            stop_price=float(stop_price or 0.0),
            correlation_id=correlation_id or str(uuid.uuid4()),
        )
    )


def auth_hello_message(
    *,
    token: str,
    client_name: str = "lumina-brain",
    client_version: str = "1.0",
    mode_context: str = "sim",
) -> fabric_pb2.BrainMessage:
    return fabric_pb2.BrainMessage(
        auth_hello=fabric_pb2.AuthHello(
            token=token,
            client_name=client_name,
            client_version=client_version,
            mode_context=mode_context,
        )
    )


def heartbeat_message(
    *,
    sequence_number: int,
    brain_status: str = "ok",
    last_known_state_hash: str = "",
) -> fabric_pb2.BrainMessage:
    return fabric_pb2.BrainMessage(
        heartbeat=fabric_pb2.Heartbeat(
            sequence_number=int(sequence_number),
            timestamp_unix_ms=_now_ms(),
            brain_status=brain_status,
            last_known_state_hash=last_known_state_hash,
        )
    )


def account_state_to_info(state: fabric_pb2.AccountState) -> AccountInfo:
    acct = state.account
    return AccountInfo(
        balance=float(acct.balance),
        equity=float(acct.equity),
        available_margin=float(acct.available_margin) if acct.available_margin else None,
        realized_pnl_today=float(acct.realized_pnl_today),
        currency=str(acct.currency or "USD"),
        raw={
            "account_name": acct.account_name,
            "safe_mode": int(state.safe_mode),
            "timestamp_unix_ms": int(state.timestamp_unix_ms),
        },
    )


def position_update_to_position(pos: fabric_pb2.PositionUpdate) -> Position | None:
    qty = int(pos.quantity)
    if qty == 0:
        return None
    side = str(pos.side or "").strip().upper()
    if not side:
        side = "BUY" if qty > 0 else "SELL"
    return Position(
        symbol=str(pos.instrument),
        quantity=abs(qty),
        avg_price=float(pos.avg_price),
        side=side,
        raw={"timestamp_unix_ms": int(pos.timestamp_unix_ms)},
    )


def order_event_to_fill(event: fabric_pb2.OrderEvent) -> Fill | None:
    """Build a Fill when the event represents a (partial) fill with price/qty."""
    filled = int(event.filled_qty)
    if filled <= 0:
        return None
    if event.state not in (
        fabric_pb2.ORDER_STATE_FILLED,
        fabric_pb2.ORDER_STATE_PARTIALLY_FILLED,
    ):
        return None
    side = order_action_to_side(event.action)
    fill_id = f"{event.nt_order_id or event.client_order_id}:{filled}:{event.timestamp_unix_ms}"
    ts = (
        time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(event.timestamp_unix_ms / 1000.0)) + "Z"
        if event.timestamp_unix_ms
        else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    return Fill(
        fill_id=fill_id,
        order_id=str(event.nt_order_id or event.client_order_id),
        symbol=str(event.instrument or ""),
        side=side,
        quantity=filled,
        price=float(event.avg_fill_price),
        timestamp=ts,
        commission=0.0,
        raw={
            "client_order_id": event.client_order_id,
            "state": int(event.state),
            "correlation_id": event.correlation_id,
        },
    )


def order_event_to_response_dict(event: fabric_pb2.OrderEvent) -> dict[str, Any]:
    if event.state == fabric_pb2.ORDER_STATE_REJECTED:
        return {
            "type": "error",
            "code": "ORDER_REJECTED",
            "message": str(event.rejection_reason or "Fabric rejected order"),
            "correlation_id": event.correlation_id,
            "client_order_id": event.client_order_id,
            "order_id": event.nt_order_id,
        }
    return {
        "type": "ack",
        "status": "ok",
        "order_id": str(event.nt_order_id or event.client_order_id),
        "client_order_id": event.client_order_id,
        "correlation_id": event.correlation_id,
        "ref_correlation_id": event.correlation_id,
        "state": int(event.state),
        "filled_qty": int(event.filled_qty),
        "avg_fill_price": float(event.avg_fill_price),
        "message": "",
    }


def command_reject_to_response_dict(reject: fabric_pb2.CommandReject) -> dict[str, Any]:
    return {
        "type": "error",
        "code": str(reject.code or "COMMAND_REJECT"),
        "message": str(reject.message or "Fabric rejected command"),
        "correlation_id": reject.correlation_id,
        "client_order_id": reject.client_order_id,
        "safe_mode": int(reject.safe_mode),
    }


def state_sync_to_domain(
    sync: fabric_pb2.StateSyncResponse,
) -> tuple[AccountInfo, list[Position], list[dict[str, Any]]]:
    account = AccountInfo(
        balance=float(sync.account.balance),
        equity=float(sync.account.equity),
        available_margin=float(sync.account.available_margin) if sync.account.available_margin else None,
        realized_pnl_today=float(sync.account.realized_pnl_today),
        currency=str(sync.account.currency or "USD"),
        raw={
            "account_name": sync.account.account_name,
            "safe_mode": int(sync.safe_mode),
            "state_hash": sync.state_hash,
        },
    )
    positions: list[Position] = []
    for p in sync.positions:
        mapped = position_update_to_position(p)
        if mapped is not None:
            positions.append(mapped)
    open_orders = [
        {
            "client_order_id": o.client_order_id,
            "nt_order_id": o.nt_order_id,
            "instrument": o.instrument,
            "quantity": int(o.quantity),
            "state": int(o.state),
            "protected": bool(o.protected),
        }
        for o in sync.open_orders
    ]
    return account, positions, open_orders
