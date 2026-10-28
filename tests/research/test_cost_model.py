"""Four-leg costs and ES/NQ vs MES/MNQ contract specs."""

from __future__ import annotations

import pytest

from lumina_research.validation.contracts import CONTRACTS, spec_for
from lumina_research.validation.cost_model import CostModel, MarketSnapshot, apply_costs


@pytest.mark.unit
def test_same_tick_different_tick_value_and_commission_ticks() -> None:
    for root in ("ES", "NQ", "MES", "MNQ"):
        spec = spec_for(root)
        assert spec.tick_size == 0.25
    assert CONTRACTS["ES"].tick_value_usd == 12.50
    assert CONTRACTS["MES"].tick_value_usd == 1.25
    assert CONTRACTS["NQ"].tick_value_usd == 5.00
    assert CONTRACTS["MNQ"].tick_value_usd == 0.50
    assert CONTRACTS["MES"].commission_ticks != CONTRACTS["ES"].commission_ticks
    assert CONTRACTS["MNQ"].commission_ticks != CONTRACTS["NQ"].commission_ticks
    assert CONTRACTS["MES"].commission_ticks > CONTRACTS["ES"].commission_ticks


@pytest.mark.unit
def test_apply_costs_stamps_all_four_legs() -> None:
    n = 8
    gross = tuple(0.01 for _ in range(n))
    positions = (1.0, 1.0, 0.0, 0.0, 1.0, 1.0, -1.0, -1.0)
    markets = tuple(MarketSnapshot(volume=5_000.0, average_volume=10_000.0, volatility_price=3.0) for _ in range(n))
    mes = apply_costs(gross_returns=gross, positions=positions, equity=50_000.0, spec="MES", markets=markets)
    es = apply_costs(gross_returns=gross, positions=positions, equity=50_000.0, spec="ES", markets=markets)
    assert mes.provenance.is_valid()
    assert mes.provenance.components == ("commission", "half_spread", "slippage", "market_impact")
    assert sum(mes.costs_usd) > 0.0
    assert sum(es.costs_usd) > sum(mes.costs_usd)
    assert all(net <= gross_i for net, gross_i in zip(mes.net_returns, mes.gross_returns))
    model = CostModel()
    fill = model.ticks_for_fill(spec=spec_for("MNQ"), quantity=2.0, market=markets[0])
    assert fill.commission_ticks > 0.0
    assert fill.half_spread_ticks == 0.5
    assert fill.slippage_ticks > 0.0
    assert fill.impact_ticks > 0.0
    assert fill.total_ticks == pytest.approx(
        fill.commission_ticks + fill.half_spread_ticks + fill.slippage_ticks + fill.impact_ticks
    )
