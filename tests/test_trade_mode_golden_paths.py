from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pandas as pd

from lumina_core.engine.operations_service import OperationsService


class _BrokerSpy:
    def __init__(self) -> None:
        self.calls = 0

    def submit_order(self, *_args: Any, **_kwargs: Any):
        self.calls += 1
        return SimpleNamespace(accepted=True, status="FILLED", message="ok")


def _build_service(mode: str) -> tuple[OperationsService, _BrokerSpy]:
    risk_ctrl: Any = MagicMock()
    risk_ctrl.check_can_trade.return_value = (True, "ok")
    risk_ctrl.apply_regime_override.return_value = None
    risk_ctrl._active_limits = SimpleNamespace(enforce_session_guard=True)

    session_guard: Any = MagicMock()
    session_guard.is_rollover_window.return_value = False
    session_guard.is_trading_session.return_value = True

    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode=mode, instrument="MES JUN26", thought_log=MagicMock()),
        app=SimpleNamespace(logger=MagicMock(), VOICE_ENABLED=False, tts_engine=None),
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=pd.DataFrame({"close": [5000.0]}),
        account_balance=50000.0,
        account_equity=50000.0,
        realized_pnl_today=0.0,
        risk_controller=risk_ctrl,
        session_guard=session_guard,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        get_current_dream_snapshot=lambda: {"signal": "BUY", "regime": "NEUTRAL", "stop": 4990.0, "target": 5020.0},
    )

    broker = _BrokerSpy()
    container = SimpleNamespace(broker=broker)

    svc = OperationsService.__new__(OperationsService)
    object.__setattr__(svc, "engine", engine)
    object.__setattr__(svc, "container", container)
    object.__setattr__(svc, "thought_queue", __import__("queue").Queue())
    from lumina_core.engine.valuation_engine import ValuationEngine

    object.__setattr__(svc, "valuation_engine", ValuationEngine())
    return svc, broker


def test_golden_path_paper_mode_no_broker_call() -> None:
    svc, broker = _build_service("paper")
    result = svc.place_order("BUY", 1)
    assert result is False
    assert broker.calls == 0


def test_golden_path_sim_mode_session_guard_blocks_outside_hours() -> None:
    svc, broker = _build_service("sim")
    svc.engine.session_guard.is_trading_session.return_value = False
    result = svc.place_order("BUY", 1)
    assert result is False
    assert broker.calls == 0


def test_golden_path_real_mode_fail_closed_without_risk_controller() -> None:
    svc, broker = _build_service("real")
    svc.engine.risk_controller = None
    svc.engine.session_guard = None
    result = svc.place_order("BUY", 1)
    assert result is False
    assert broker.calls == 0


def test_golden_path_sim_real_guard_mode_session_guard_blocks_outside_hours() -> None:
    svc, broker = _build_service("sim_real_guard")
    svc.engine.session_guard.is_trading_session.return_value = False
    result = svc.place_order("BUY", 1)
    assert result is False
    assert broker.calls == 0


def test_golden_path_sim_real_guard_mode_blocks_risk_breach() -> None:
    svc, broker = _build_service("sim_real_guard")
    with patch("lumina_core.engine.operations_service.enforce_pre_trade_gate", return_value=(False, "daily_loss_cap")):
        result = svc.place_order("BUY", 1)
    assert result is False
    assert broker.calls == 0


def test_is_market_open_uses_session_guard_only() -> None:
    svc, _broker = _build_service("sim")
    svc.engine.session_guard.is_trading_session.return_value = True
    assert svc.is_market_open() is True
    svc.engine.session_guard.is_trading_session.assert_called_once()


def test_is_market_open_fail_closed_when_session_guard_unavailable() -> None:
    svc, _broker = _build_service("real")
    svc.engine.session_guard = None

    assert svc.is_market_open() is False
    svc.engine.app.logger.warning.assert_called_with("OPS_MARKET_OPEN_FAIL_CLOSED,error_code=SESSION_GUARD_UNAVAILABLE")


def test_is_market_open_fail_closed_when_session_guard_errors() -> None:
    svc, _broker = _build_service("real")
    svc.engine.session_guard.is_trading_session.side_effect = RuntimeError("guard down")

    assert svc.is_market_open() is False
    svc.engine.app.logger.warning.assert_called()
    logged_message = str(svc.engine.app.logger.warning.call_args[0][0])
    assert "OPS_MARKET_OPEN_FAIL_CLOSED" in logged_message
    assert "SESSION_GUARD_ERROR" in logged_message
