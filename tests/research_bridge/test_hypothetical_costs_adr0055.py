"""D3: hypothetical fills use ADR-0055 commission; slippage in fill price; execution-side wins."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.market.nt_fees import all_in_per_side_usd, spec_for
from lumina_core.research_bridge.costs import hypothetical_execution_costs, tick_value_usd
from tests.research_bridge.helpers import make_runtime, sealed_candidate


@pytest.mark.unit
def test_mes_and_es_commissions_match_nt_card() -> None:
    assert all_in_per_side_usd("MES", qty=1) == pytest.approx(0.94)
    assert all_in_per_side_usd("ES", qty=1) == pytest.approx(2.87)
    assert all_in_per_side_usd("MNQ", qty=1) == pytest.approx(0.94)
    assert all_in_per_side_usd("NQ", qty=1) == pytest.approx(2.87)
    mes = hypothetical_execution_costs(instrument="MES", direction="BUY", size=1.0, reference_price=5000.0)
    es = hypothetical_execution_costs(instrument="ES", direction="BUY", size=1.0, reference_price=5000.0)
    assert mes.commission_usd == pytest.approx(0.94)
    assert es.commission_usd == pytest.approx(2.87)
    assert mes.commission_usd != es.commission_usd


@pytest.mark.unit
def test_mnq_nq_tick_values_differ_and_slippage_is_in_fill_price() -> None:
    assert tick_value_usd("MES") == pytest.approx(1.25)
    assert tick_value_usd("ES") == pytest.approx(12.50)
    assert tick_value_usd("MNQ") == pytest.approx(0.50)
    assert tick_value_usd("NQ") == pytest.approx(5.00)
    mnq = hypothetical_execution_costs(instrument="MNQ", direction="BUY", size=1.0, reference_price=20_000.0)
    nq = hypothetical_execution_costs(instrument="NQ", direction="BUY", size=1.0, reference_price=20_000.0)
    mes_sell = hypothetical_execution_costs(instrument="MES", direction="SELL", size=1.0, reference_price=5000.0)
    assert mnq.slippage_usd == pytest.approx(0.50)
    assert nq.slippage_usd == pytest.approx(5.00)
    assert mnq.tick_value_usd != nq.tick_value_usd
    assert mnq.fill_price == pytest.approx(20_000.0 + spec_for("MNQ").tick_size)
    assert mes_sell.fill_price == pytest.approx(5000.0 - spec_for("MES").tick_size)
    assert mnq.slippage_ticks == pytest.approx(1.0)
    assert nq.commission_usd == pytest.approx(2.87)
    assert mnq.commission_usd == pytest.approx(0.94)


@pytest.mark.unit
def test_fill_event_uses_execution_side_even_on_discrepancy(tmp_path: Path) -> None:
    _bus, authority, runtime, _alerts, _observe = make_runtime(tmp_path, healthy=True, close=5000.0)
    intent = runtime.on_candidate(sealed_candidate(authority, instrument="MES"))
    assert intent is not None
    fills = runtime.issued_fills()
    assert len(fills) == 1
    fill = fills[0]
    costs = hypothetical_execution_costs(
        instrument="MES", direction="BUY", size=1.0, reference_price=5000.0
    )
    assert fill.fill_price == pytest.approx(costs.fill_price)
    assert fill.qty == 1
    assert fill.commission == pytest.approx(costs.commission_usd)
    assert fill.slippage_ticks == pytest.approx(costs.slippage_ticks)
    assert fill.slippage_usd == pytest.approx(costs.slippage_usd)
    assert fill.commission_ticks == pytest.approx(costs.commission_ticks)
    assert fill.source == "hypothetical_adr0055"
    if costs.discrepancy:
        assert costs.research_total_usd is not None
        assert fill.commission + fill.slippage_usd == pytest.approx(costs.commission_usd + costs.slippage_usd)
    jsonl = (tmp_path / "research_shadow.jsonl").read_text(encoding="utf-8")
    assert '"source": "hypothetical_adr0055"' in jsonl
    assert '"cost_discrepancy":' in jsonl


@pytest.mark.unit
def test_invalid_reference_or_size_fail_closed() -> None:
    with pytest.raises(ValueError, match="reference_price"):
        hypothetical_execution_costs(instrument="MES", direction="BUY", size=1.0, reference_price=0.0)
    with pytest.raises(ValueError, match="size"):
        hypothetical_execution_costs(instrument="MES", direction="BUY", size=0.0, reference_price=5000.0)
    with pytest.raises(ValueError, match="quantity"):
        hypothetical_execution_costs(instrument="MES", direction="BUY", size=1.0, reference_price=5000.0, qty=0)
    fractional = hypothetical_execution_costs(
        instrument="MES", direction="BUY", size=0.4, reference_price=5000.0
    )
    assert fractional.commission_usd == pytest.approx(0.94)
