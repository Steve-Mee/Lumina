"""Unit tests for Execution Fabric domain ↔ protobuf mapping."""

from __future__ import annotations

import pytest

pytest.importorskip("grpc")

from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.broker.ninjatrader import fabric_mapper as mapper
from lumina_core.broker.ninjatrader.generated import fabric_pb2


def test_order_to_place_command_maps_core_fields() -> None:
    order = Order(symbol="MNQ", side="BUY", quantity=2, order_type="LIMIT", stop_loss=21000.0)
    order.metadata["price"] = 21050.25
    cmd = mapper.order_to_place_command(
        order,
        client_order_id="cid-1",
        correlation_id="corr-1",
        mode_context="sim",
    )
    assert cmd.instrument == "MNQ"
    assert cmd.action == fabric_pb2.ORDER_ACTION_BUY
    assert cmd.quantity == 2
    assert cmd.order_type == fabric_pb2.ORDER_TYPE_LIMIT
    assert cmd.price == pytest.approx(21050.25)
    assert cmd.stop_price == pytest.approx(21000.0)
    assert cmd.client_order_id == "cid-1"
    assert cmd.mode_context == "sim"


def test_order_event_to_response_ack_and_reject() -> None:
    ok = fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt-9",
        state=fabric_pb2.ORDER_STATE_WORKING,
        correlation_id="corr",
    )
    resp = mapper.order_event_to_response_dict(ok)
    assert resp["type"] == "ack"
    assert resp["order_id"] == "nt-9"

    bad = fabric_pb2.OrderEvent(
        client_order_id="c1",
        state=fabric_pb2.ORDER_STATE_REJECTED,
        rejection_reason="size",
        correlation_id="corr",
    )
    err = mapper.order_event_to_response_dict(bad)
    assert err["type"] == "error"
    assert "size" in err["message"]


def test_order_event_to_fill_only_on_fill_states() -> None:
    working = fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt1",
        state=fabric_pb2.ORDER_STATE_WORKING,
        filled_qty=0,
        instrument="MNQ",
        action=fabric_pb2.ORDER_ACTION_BUY,
    )
    assert mapper.order_event_to_fill(working) is None

    filled = fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt1",
        state=fabric_pb2.ORDER_STATE_FILLED,
        filled_qty=1,
        avg_fill_price=100.5,
        instrument="MNQ",
        action=fabric_pb2.ORDER_ACTION_BUY,
        timestamp_unix_ms=1_700_000_000_000,
    )
    fill = mapper.order_event_to_fill(filled)
    assert fill is not None
    assert fill.quantity == 1
    assert fill.price == pytest.approx(100.5)
    assert fill.side == "BUY"
