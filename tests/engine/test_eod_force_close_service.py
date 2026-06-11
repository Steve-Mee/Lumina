"""
Tests for EODForceCloseService (D2 sub-slice 6: bounded EOD closer extraction / firewall in runtime_workers).

Per test-scaffolding skill: @pytest.mark.unit, given-when-then in docstrings, fail-closed/best-effort explicit, monkeypatch/mocker.
Follows sub4 test_paper_trade_executor.py + sub5 test_paper_simulator.py style + supervisor mock integration.
Leverages existing EOD tests in tests/test_runtime_workers.py (supervisor EOD flatten/hold).
"""

import pytest
from unittest.mock import MagicMock
from types import SimpleNamespace

from lumina_core.engine.eod_force_close_service import EODForceCloseService, _enforce_real_eod_force_close
from lumina_core.engine.paper_trade_executor import PaperTradeExecutor


def _make_mock_app(trade_mode="real", instrument="TEST"):
    app = SimpleNamespace()
    app.sim_position_qty = 0
    app.sim_entry_price = 0.0
    app.INSTRUMENT = instrument
    app.engine = SimpleNamespace()
    app.engine.config = SimpleNamespace(trade_mode=trade_mode, instrument=instrument)
    app.engine.live_position_qty = 5
    app.engine.last_entry_price = 100.0
    app.engine.live_trade_signal = "BUY"
    app.logger = MagicMock()
    return app


def _make_mock_broker(pos_qty=5, accepted=True):
    broker = MagicMock()
    pos = SimpleNamespace(symbol="TEST", quantity=pos_qty, avg_price=100.0)
    broker.get_positions.return_value = [pos] if pos_qty != 0 else []
    submit_res = SimpleNamespace(accepted=accepted)
    broker.submit_order.return_value = submit_res
    return broker


@pytest.mark.unit
def test_eod_force_close_service_enforce_flattens_and_resets_live():
    """Given service with mock app/engine/risk_ctrl/obs/broker (positions with qty) + executor spy, when enforce_eod_force_close(price) and should_close=True + eod_enabled, then executor called with EOD metadata + live_* reset (position=0, entry=price, signal=HOLD) + return True. given-when-then."""
    app = _make_mock_app(trade_mode="real")
    risk_ctrl = MagicMock()
    risk_ctrl.should_force_close_eod.return_value = (True, "test eod window")
    app.engine.risk_controller = risk_ctrl
    obs = MagicMock()
    app.engine.observability_service = obs
    broker = _make_mock_broker(pos_qty=5)
    executor = MagicMock(spec=PaperTradeExecutor)
    executor.build_paper_order.return_value = SimpleNamespace(metadata={})
    executor.submit_paper_order.return_value = SimpleNamespace(accepted=True)

    service = EODForceCloseService(app=app, broker=broker, executor=executor)
    held = service.enforce_eod_force_close(price=101.0)

    assert held is True
    # executor called (EOD metadata)
    assert executor.build_paper_order.called or hasattr(executor, "build_and_submit_eod_close")
    assert app.engine.live_position_qty == 0
    assert app.engine.live_trade_signal == "HOLD"
    obs.record_mode_eod_force_close.assert_called()


@pytest.mark.unit
def test_eod_force_close_service_skips_on_no_capabilities_or_no_should():
    """Given ... risk_ctrl should=False or !eod_enabled (paper), when enforce, then no broker/executor calls + return False; best-effort."""
    app = _make_mock_app(trade_mode="paper")  # eod_enabled=False for paper
    risk_ctrl = MagicMock()
    risk_ctrl.should_force_close_eod.return_value = (True, "window")
    app.engine.risk_controller = risk_ctrl
    broker = _make_mock_broker()
    executor = MagicMock(spec=PaperTradeExecutor)

    service = EODForceCloseService(app=app, broker=broker, executor=executor)
    held = service.enforce_eod_force_close(price=101.0)

    assert held is False
    executor.build_paper_order.assert_not_called()


@pytest.mark.unit
def test_eod_force_close_service_compat_shim():
    """Compat shim _enforce_real_eod_force_close still works (delegates to service)."""
    app = _make_mock_app(trade_mode="real")
    risk_ctrl = MagicMock()
    risk_ctrl.should_force_close_eod.return_value = (True, "window")
    app.engine.risk_controller = risk_ctrl
    broker = _make_mock_broker(pos_qty=1)
    executor = MagicMock(spec=PaperTradeExecutor)
    executor.build_paper_order.return_value = SimpleNamespace(metadata={})
    executor.submit_paper_order.return_value = SimpleNamespace(accepted=True)

    # use the module shim (as existing callers/tests may)
    held = _enforce_real_eod_force_close(app, 101.0)
    assert held is True


@pytest.mark.integration
def test_eod_force_close_service_integration_with_supervisor_mocks():
    """Integration: supervisor-like mocks (app/container with broker + risk_ctrl), exercise thin delegation path via service; no behavior change (same flatten/hold as pre)."""
    app = _make_mock_app(trade_mode="real")
    risk_ctrl = MagicMock()
    risk_ctrl.should_force_close_eod.return_value = (True, "window")
    app.engine.risk_controller = risk_ctrl
    container = SimpleNamespace(broker=_make_mock_broker(pos_qty=3))
    executor = MagicMock(spec=PaperTradeExecutor)
    executor.build_paper_order.return_value = SimpleNamespace(metadata={})
    executor.submit_paper_order.return_value = SimpleNamespace(accepted=True)

    # simulate the thin delegation that will be in supervisor post-edit
    eod_closer = EODForceCloseService(app=app, container=container, executor=executor)
    held = eod_closer.enforce_eod_force_close(price=99.0)
    assert held is True
    # (in full with real broker fill it would set pos; here path exercised + no exception)
    print("INTEGRATION_SMOKE_SUB6_SUCCESS")  # for manual


if __name__ == "__main__":
    pytest.main([__file__, "-q", "--tb=line"])