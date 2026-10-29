"""BUY fill 1 tick above reference → slippage_ticks=1, slippage_usd=tick_value."""

from __future__ import annotations

import pytest

pytest.importorskip("grpc")

from lumina_core.broker.ninjatrader import fabric_mapper as mapper
from lumina_core.broker.ninjatrader.generated import fabric_pb2
from lumina_core.market.nt_fees import spec_for


@pytest.mark.unit
@pytest.mark.safety_gate
def test_buy_one_tick_adverse_mes() -> None:
    tick = float(spec_for("MES").tick_size)
    event = fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt1",
        state=fabric_pb2.ORDER_STATE_FILLED,
        filled_qty=1,
        avg_fill_price=5000.0 + tick,
        instrument="MES",
        action=fabric_pb2.ORDER_ACTION_BUY,
        timestamp_unix_ms=1_700_000_000_000,
    )
    fill = mapper.order_event_to_fill(event, reference_price=5000.0)
    assert fill is not None
    assert fill.slippage_ticks == pytest.approx(1.0)
    assert fill.slippage_usd == pytest.approx(1.25)
    assert "slippage_ticks" in fill.raw


@pytest.mark.unit
def test_slippage_omitted_without_reference() -> None:
    event = fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt1",
        state=fabric_pb2.ORDER_STATE_FILLED,
        filled_qty=1,
        avg_fill_price=5000.25,
        instrument="MES",
        action=fabric_pb2.ORDER_ACTION_BUY,
        timestamp_unix_ms=1_700_000_000_000,
    )
    fill = mapper.order_event_to_fill(event)
    assert fill is not None
    assert fill.slippage_ticks is None
    assert fill.slippage_usd is None
    assert "slippage_ticks" not in fill.raw


@pytest.mark.unit
def test_sell_one_tick_adverse_mes() -> None:
    tick = float(spec_for("MES").tick_size)
    event = fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt1",
        state=fabric_pb2.ORDER_STATE_FILLED,
        filled_qty=1,
        avg_fill_price=5000.0 - tick,
        instrument="MES",
        action=fabric_pb2.ORDER_ACTION_SELL,
        timestamp_unix_ms=1_700_000_000_000,
    )
    fill = mapper.order_event_to_fill(event, reference_price=5000.0)
    assert fill is not None
    assert fill.slippage_ticks == pytest.approx(1.0)
    assert fill.slippage_usd == pytest.approx(1.25)
