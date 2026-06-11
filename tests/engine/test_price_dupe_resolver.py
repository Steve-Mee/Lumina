"""
Tests for PriceDupeResolver (D2 sub-slice 12).

Per test-scaffolding skill: @pytest.mark.unit, given-when-then, fail-closed/best-effort paths, monkeypatch/mocker for deps.
Mirrors sub4-11 style (e.g. test_supervisor_phase_state_machine.py, test_live_position_manager.py) + existing supervisor/paper tests.
"""

import pytest
from types import SimpleNamespace
from contextlib import nullcontext

from lumina_core.engine.price_dupe_resolver import PriceDupeResolver


@pytest.mark.unit
class TestPriceDupeResolver:
    @pytest.fixture
    def mock_app_with_quotes(self):
        app = SimpleNamespace(
            live_data_lock=nullcontext(),
            live_quotes=[{"last": 12345.67}],
            ohlc_1min=None,
            engine=SimpleNamespace(
                sim_position_qty=0,
                sim_entry_price=0.0,
                config=SimpleNamespace(instrument="TEST"),
            ),
            INSTRUMENT="TEST",
        )
        return app

    @pytest.fixture
    def mock_app_with_ohlc(self):
        import pandas as pd
        app = SimpleNamespace(
            live_data_lock=nullcontext(),
            live_quotes=None,
            ohlc_1min=pd.DataFrame({"close": [9999.99]}),
            engine=SimpleNamespace(
                sim_position_qty=0,
                sim_entry_price=0.0,
                config=SimpleNamespace(instrument="TEST"),
            ),
            INSTRUMENT="TEST",
        )
        return app

    @pytest.fixture
    def mock_app_empty(self):
        app = SimpleNamespace(
            live_data_lock=nullcontext(),
            live_quotes=None,
            ohlc_1min=None,
            engine=SimpleNamespace(
                sim_position_qty=0,
                sim_entry_price=0.0,
                config=SimpleNamespace(instrument="TEST"),
            ),
            INSTRUMENT="TEST",
        )
        return app

    def test_fetch_locked_price_happy_from_quotes(self, mock_app_with_quotes):
        # gegeven
        resolver = PriceDupeResolver(app=mock_app_with_quotes)
        # wanneer
        price = resolver.fetch_locked_price()
        # dan
        assert price == 12345.67

    def test_fetch_locked_price_fallback_to_ohlc_and_zero(self, mock_app_with_ohlc, mock_app_empty):
        # gegeven
        resolver_ohlc = PriceDupeResolver(app=mock_app_with_ohlc)
        resolver_empty = PriceDupeResolver(app=mock_app_empty)
        # wanneer
        price_ohlc = resolver_ohlc.fetch_locked_price()
        price_empty = resolver_empty.fetch_locked_price()
        # dan
        assert price_ohlc == 9999.99
        assert price_empty == 0.0

    def test_fetch_locked_price_graceful_on_missing_lock_quotes_ohlc(self):
        # gegeven
        app = SimpleNamespace(
            live_data_lock=None,  # triggers nullcontext path
            live_quotes=None,
            ohlc_1min=None,
            engine=SimpleNamespace(sim_position_qty=0, sim_entry_price=0.0, config=SimpleNamespace(instrument="TEST")),
            INSTRUMENT="TEST",
        )
        resolver = PriceDupeResolver(app=app)
        # wanneer
        price = resolver.fetch_locked_price()
        # dan
        assert price == 0.0  # fail-closed best-effort

    def test_paper_shims_delegate_and_compat(self, mock_app_with_quotes):
        # gegeven
        resolver = PriceDupeResolver(app=mock_app_with_quotes)
        mock_broker = SimpleNamespace()
        # (for sync/store/clear, we just assert no crash + compat sets; full broker mock in integration)
        # wanneer
        inst = resolver.paper_instrument()
        resolver.paper_sync_sim_from_broker(mock_broker, "TEST")
        resolver.paper_store_round_ledger_from_last_fill(mock_broker, "TEST", "BUY")
        resolver.paper_clear_round_ledger()
        # dan
        assert inst == "TEST"
        # compat sets happened in sync (even if broker has no last_fill)
        assert mock_app_with_quotes.sim_position_qty == 0
        assert mock_app_with_quotes.sim_entry_price == 0.0
        # MANUAL_SMOKE_SUB12_PRICE_DUPE_SUCCESS

    def test_paper_shims_graceful_fallback(self, mock_app_empty):
        # gegeven
        resolver = PriceDupeResolver(app=mock_app_empty)
        # (no broker last_fill etc.)
        # wanneer / dan
        assert resolver.paper_instrument() == "TEST"
        resolver.paper_sync_sim_from_broker(None, "TEST")  # no crash
        resolver.paper_store_round_ledger_from_last_fill(None, "TEST", "SELL")  # no crash
        resolver.paper_clear_round_ledger()  # no crash
        # MANUAL_SMOKE_SUB12_PRICE_DUPE_SUCCESS

    def test_fetch_locked_price_and_ohlc_returns_copy(self, mock_app_with_quotes):
        import pandas as pd

        mock_app_with_quotes.ohlc_1min = pd.DataFrame({"close": [100.0, 200.0]})
        resolver = PriceDupeResolver(app=mock_app_with_quotes)
        price, df = resolver.fetch_locked_price_and_ohlc()
        assert price == 12345.67
        assert df is not None
        assert len(df) == 2
        mock_app_with_quotes.ohlc_1min.loc[0, "close"] = 999.0
        assert float(df.iloc[0]["close"]) == 100.0

    # Integration note: extend existing tests/test_runtime_workers.py + paper tests (still pass + asserts on resolver or post-price/ledger)
    # "MANUAL_SMOKE_SUB12_PRICE_DUPE_SUCCESS" (full mocks + thin from supervisor-mock + paper call sites in broader k)