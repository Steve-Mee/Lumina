"""Mapper stamps ADR-0055 Free-plan all-in. Never 0.0."""

from __future__ import annotations

import pytest

pytest.importorskip("grpc")

from lumina_core.broker.ninjatrader import fabric_mapper as mapper
from lumina_core.broker.ninjatrader.generated import fabric_pb2


def _filled(instrument: str, qty: int = 1, price: float = 100.5) -> fabric_pb2.OrderEvent:
    return fabric_pb2.OrderEvent(
        client_order_id="c1",
        nt_order_id="nt1",
        state=fabric_pb2.ORDER_STATE_FILLED,
        filled_qty=qty,
        avg_fill_price=price,
        instrument=instrument,
        action=fabric_pb2.ORDER_ACTION_BUY,
        timestamp_unix_ms=1_700_000_000_000,
    )


@pytest.mark.unit
@pytest.mark.safety_gate
def test_mes_es_mnq_nq_commissions() -> None:
    mes = mapper.order_event_to_fill(_filled("MES"))
    es = mapper.order_event_to_fill(_filled("ES"))
    mnq = mapper.order_event_to_fill(_filled("MNQ"))
    nq = mapper.order_event_to_fill(_filled("NQ"))
    assert mes is not None and es is not None and mnq is not None and nq is not None
    assert mes.commission == pytest.approx(0.94)
    assert es.commission == pytest.approx(2.87)
    assert mnq.commission == pytest.approx(0.94)
    assert nq.commission == pytest.approx(2.87)
    assert mnq.commission != nq.commission
    assert mes.commission != 0.0
    assert es.commission_ticks == pytest.approx(2.87 / 12.50)
    mes2 = mapper.order_event_to_fill(_filled("MES", qty=2))
    assert mes2 is not None
    assert mes2.commission == pytest.approx(1.88)


@pytest.mark.unit
def test_unknown_root_is_not_stamped_zero() -> None:
    fill = mapper.order_event_to_fill(_filled("NOTAROOT"))
    assert fill is None
