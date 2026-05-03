"""Tests for TradeExecutionCostModel and CostBreakdown.

All tests are unit-level: no I/O, no network, no external services.
"""

from __future__ import annotations

import pytest

from lumina_core.risk.cost_model import (
    TradeExecutionCostModel,
    _instrument_tick_params,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mes_model() -> TradeExecutionCostModel:
    """Standard MES cost model with realistic parameters."""
    return TradeExecutionCostModel(
        tick_size=0.25,
        tick_value=1.25,
        commission_per_side_usd=1.29,
        exchange_fee_per_side_usd=0.35,
        clearing_fee_per_side_usd=0.10,
        nfa_fee_per_side_usd=0.02,
        slippage_base_ticks=0.5,
        slippage_atr_ratio=0.10,
        slippage_sigma=0.0,
        spread_multipliers={"open": 2.5, "midday": 1.0, "close": 2.0},
        market_impact_alpha=0.5,
        market_impact_beta=0.6,
        instrument="MES",
    )


# ---------------------------------------------------------------------------
# Fee calculation tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFees:
    def test_fees_per_side_sum_is_correct(self, mes_model: TradeExecutionCostModel):
        expected = 1.29 + 0.35 + 0.10 + 0.02
        assert mes_model.fees_usd_per_side() == pytest.approx(expected, rel=1e-6)

    def test_fees_scale_with_quantity(self, mes_model: TradeExecutionCostModel):
        cost_1 = mes_model.cost_for_trade(price=5000.0, quantity=1.0, atr=0.0)
        cost_2 = mes_model.cost_for_trade(price=5000.0, quantity=2.0, atr=0.0)
        assert cost_2.total_fees_usd_per_side == pytest.approx(cost_1.total_fees_usd_per_side * 2, rel=1e-6)

    def test_round_trip_is_twice_per_side(self, mes_model: TradeExecutionCostModel):
        cost = mes_model.cost_for_trade(price=5000.0, quantity=1.0, atr=5.0)
        assert cost.total_round_trip_usd == pytest.approx(cost.total_per_side_usd * 2, rel=1e-6)

    def test_commission_component_correct(self, mes_model: TradeExecutionCostModel):
        cost = mes_model.cost_for_trade(price=5000.0, quantity=1.0, atr=0.0)
        assert cost.commission_usd_per_side == pytest.approx(1.29, rel=1e-6)

    def test_exchange_clearing_nfa_correct(self, mes_model: TradeExecutionCostModel):
        cost = mes_model.cost_for_trade(price=5000.0, quantity=1.0, atr=0.0)
        assert cost.exchange_fee_usd_per_side == pytest.approx(0.35, rel=1e-6)
        assert cost.clearing_fee_usd_per_side == pytest.approx(0.10, rel=1e-6)
        assert cost.nfa_fee_usd_per_side == pytest.approx(0.02, rel=1e-6)


# ---------------------------------------------------------------------------
# Slippage tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSlippage:
    def test_spread_ticks_wider_at_open(self, mes_model: TradeExecutionCostModel):
        spread_open = mes_model._spread_ticks(atr=8.0, time_period="open")
        spread_mid = mes_model._spread_ticks(atr=8.0, time_period="midday")
        assert spread_open > spread_mid

    def test_spread_ticks_wider_at_close(self, mes_model: TradeExecutionCostModel):
        spread_close = mes_model._spread_ticks(atr=8.0, time_period="close")
        spread_mid = mes_model._spread_ticks(atr=8.0, time_period="midday")
        assert spread_close > spread_mid

    def test_spread_floor_applied(self, mes_model: TradeExecutionCostModel):
        """Zero ATR should still return slippage_base_ticks floor."""
        spread = mes_model._spread_ticks(atr=0.0, time_period="midday")
        assert spread >= mes_model.slippage_base_ticks

    def test_market_impact_zero_when_no_volume(self, mes_model: TradeExecutionCostModel):
        impact = mes_model._market_impact_ticks(quantity=1.0, avg_volume=0.0)
        assert impact == 0.0

    def test_market_impact_zero_for_zero_quantity(self, mes_model: TradeExecutionCostModel):
        impact = mes_model._market_impact_ticks(quantity=0.0, avg_volume=5000.0)
        assert impact == 0.0

    def test_market_impact_increases_with_quantity(self, mes_model: TradeExecutionCostModel):
        small = mes_model._market_impact_ticks(quantity=1.0, avg_volume=5000.0)
        large = mes_model._market_impact_ticks(quantity=50.0, avg_volume=5000.0)
        assert large > small

    def test_total_slippage_ticks_positive(self, mes_model: TradeExecutionCostModel):
        ticks = mes_model.slippage_ticks(atr=8.0, quantity=1.0, avg_volume=5000.0)
        assert ticks > 0.0

    def test_slippage_usd_uses_tick_value(self, mes_model: TradeExecutionCostModel):
        cost = mes_model.cost_for_trade(price=5000.0, quantity=1.0, atr=8.0, avg_volume=5000.0)
        expected_usd = cost.total_slippage_ticks * mes_model.tick_value * 1.0
        assert cost.slippage_usd_per_side == pytest.approx(expected_usd, rel=1e-6)


# ---------------------------------------------------------------------------
# Round-trip totals
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRoundTripCost:
    def test_round_trip_includes_all_components(self, mes_model: TradeExecutionCostModel):
        cost = mes_model.cost_for_trade(price=5020.0, quantity=1.0, atr=8.0, avg_volume=5000.0)
        expected_rt = (cost.slippage_usd_per_side + cost.total_fees_usd_per_side) * 2.0
        assert cost.total_round_trip_usd == pytest.approx(expected_rt, rel=1e-6)

    def test_net_pnl_deducts_round_trip(self, mes_model: TradeExecutionCostModel):
        gross_pnl = 100.0
        net = mes_model.net_pnl(gross_pnl_usd=gross_pnl, quantity=1.0, atr=0.0)
        cost = mes_model.cost_for_trade(price=0.0, quantity=1.0, atr=0.0)
        assert net == pytest.approx(gross_pnl - cost.total_round_trip_usd, rel=1e-6)

    def test_net_pnl_can_be_negative(self, mes_model: TradeExecutionCostModel):
        """A very small trade can result in negative net PnL after costs."""
        net = mes_model.net_pnl(gross_pnl_usd=0.50, quantity=1.0, atr=0.0)
        assert net < 0.50

    def test_breakeven_move_ticks_positive(self, mes_model: TradeExecutionCostModel):
        cost = mes_model.cost_for_trade(price=5020.0, quantity=1.0, atr=8.0, avg_volume=5000.0)
        assert cost.breakeven_move_ticks > 0.0

    def test_cost_breakdown_meta_fields(self, mes_model: TradeExecutionCostModel):
        cost = mes_model.cost_for_trade(price=5020.0, quantity=2.0, atr=8.0, avg_volume=5000.0, time_period="open")
        assert cost.instrument == "MES"
        assert cost.quantity == 2.0
        assert cost.price == 5020.0
        assert cost.atr == 8.0
        assert cost.time_period == "open"


# ---------------------------------------------------------------------------
# from_config factory
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFromConfig:
    def test_from_dict_config(self):
        cfg = {
            "risk_controller": {
                "commission_per_side_usd": 1.50,
                "exchange_fee_per_side_usd": 0.40,
                "clearing_fee_per_side_usd": 0.12,
                "nfa_fee_per_side_usd": 0.03,
                "order_book_spread_atr_ratio": 0.08,
                "market_impact_alpha": 0.4,
                "market_impact_beta": 0.55,
            }
        }
        model = TradeExecutionCostModel.from_config(cfg, instrument="MES")
        assert model.commission_per_side_usd == pytest.approx(1.50)
        assert model.exchange_fee_per_side_usd == pytest.approx(0.40)
        assert model.slippage_atr_ratio == pytest.approx(0.08)

    def test_from_config_instrument_tick_params(self):
        model = TradeExecutionCostModel.from_config({}, instrument="ES")
        assert model.tick_size == pytest.approx(0.25)
        assert model.tick_value == pytest.approx(12.50)

    def test_from_config_unknown_instrument_falls_back_to_mes(self):
        model = TradeExecutionCostModel.from_config({}, instrument="UNKNOWN")
        assert model.tick_size == pytest.approx(0.25)
        assert model.tick_value == pytest.approx(1.25)


# ---------------------------------------------------------------------------
# Instrument registry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInstrumentRegistry:
    @pytest.mark.parametrize(
        "symbol,tick_size,tick_value",
        [
            ("MES", 0.25, 1.25),
            ("ES", 0.25, 12.50),
            ("MNQ", 0.25, 0.50),
            ("NQ", 0.25, 5.00),
            ("MYM", 1.00, 0.50),
            ("YM", 1.00, 5.00),
            ("MCL", 0.01, 1.00),
            ("GC", 0.10, 10.00),
        ],
    )
    def test_instrument_tick_params(self, symbol: str, tick_size: float, tick_value: float):
        ts, tv = _instrument_tick_params(symbol)
        assert ts == pytest.approx(tick_size), f"{symbol}: tick_size mismatch"
        assert tv == pytest.approx(tick_value), f"{symbol}: tick_value mismatch"

    def test_expiry_suffix_stripped(self):
        ts, tv = _instrument_tick_params("MES JUN26")
        assert ts == pytest.approx(0.25)
        assert tv == pytest.approx(1.25)

    def test_lowercase_symbol_works(self):
        ts, tv = _instrument_tick_params("mes")
        assert ts == pytest.approx(0.25)
