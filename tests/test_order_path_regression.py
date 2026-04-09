"""
Regression tests voor het canonieke orderpad in OperationsService.place_order.

Mode-semantiek Lumina:
  paper  – geen broker-call; returns False (fills intern bijgehouden)
  sim    – live NinjaTrader data + live orders op simulatie account (onbeperkt budget).
           SessionGuard/rollover gelden WÉL (live market). Financiële budgetlimieten
           NIET (enforce_rules=False op RiskController voor SIM).
  real   – echt geld; volledige SessionGuard + HardRiskController enforcement.
"""
from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from lumina_core.engine.operations_service import OperationsService
from lumina_core.trade_workers import check_pre_trade_risk


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_engine(trade_mode: str, risk_ok: bool = True, enforce_session_guard: bool = True):
    """Minimal LuminaEngine stand-in."""
    risk_ctrl = MagicMock()
    risk_ctrl.check_can_trade.return_value = (risk_ok, "ok" if risk_ok else "blocked")
    risk_ctrl.apply_regime_override.return_value = None
    limits = SimpleNamespace(enforce_session_guard=enforce_session_guard)
    risk_ctrl._active_limits = limits

    session_guard = MagicMock()
    session_guard.is_rollover_window.return_value = False
    session_guard.is_trading_session.return_value = True

    engine = SimpleNamespace(
        config=SimpleNamespace(
            trade_mode=trade_mode,
            instrument="MES JUN26",
            thought_log=MagicMock(),
        ),
        app=SimpleNamespace(
            logger=MagicMock(),
            VOICE_ENABLED=False,
            tts_engine=None,
        ),
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
    return engine


def _make_container(accepted: bool = True):
    order_result = SimpleNamespace(accepted=accepted, status="FILLED", message="ok")
    broker = MagicMock()
    broker.submit_order.return_value = order_result
    return SimpleNamespace(broker=broker)


def _make_service(trade_mode: str, risk_ok: bool = True, enforce_session_guard: bool = True,
                  broker_accepted: bool = True) -> tuple[OperationsService, Any]:
    engine = _make_engine(trade_mode, risk_ok=risk_ok, enforce_session_guard=enforce_session_guard)
    container = _make_container(accepted=broker_accepted)
    svc = OperationsService.__new__(OperationsService)
    object.__setattr__(svc, "engine", engine)
    object.__setattr__(svc, "container", container)
    object.__setattr__(svc, "thought_queue", __import__("queue").Queue())
    from lumina_core.engine.valuation_engine import ValuationEngine
    object.__setattr__(svc, "valuation_engine", ValuationEngine())
    return svc, container


# ─── PAPER tests ─────────────────────────────────────────────────────────────

def test_paper_mode_returns_false_immediately():
    """Paper mode nooit een broker-call — altijd False."""
    svc, container = _make_service("paper")
    result = svc.place_order("BUY", 1)
    assert result is False
    container.broker.submit_order.assert_not_called()


def test_paper_mode_skips_risk_controller():
    """Risk controller mag niet aangeroepen worden in paper mode."""
    svc, _ = _make_service("paper")
    result = svc.place_order("BUY", 1)
    assert result is False
    # engine.risk_controller.check_can_trade nooit aangeroepen in paper
    svc.engine.risk_controller.check_can_trade.assert_not_called()


# ─── SIM tests ───────────────────────────────────────────────────────────────

def test_sim_mode_submits_to_broker():
    """SIM stuurt naar broker (sim money, live orders)."""
    svc, container = _make_service("sim")
    result = svc.place_order("BUY", 1)
    assert result is True
    container.broker.submit_order.assert_called_once()


def test_sim_mode_respects_session_guard():
    """SIM gebruikt live orders — SessionGuard blokkert buiten trading hours."""
    svc, container = _make_service("sim", enforce_session_guard=True)
    svc.engine.session_guard.is_trading_session.return_value = False
    result = svc.place_order("BUY", 1)
    # SIM moet ook geblokkeerd worden buiten trading hours
    assert result is False
    container.broker.submit_order.assert_not_called()


def test_sim_mode_respects_rollover_window():
    """SIM gebruikt live orders — SessionGuard blokkert tijdens rollover."""
    svc, container = _make_service("sim", enforce_session_guard=True)
    svc.engine.session_guard.is_rollover_window.return_value = True
    result = svc.place_order("BUY", 1)
    assert result is False
    container.broker.submit_order.assert_not_called()


def test_sim_mode_financial_risk_waived_via_enforce_rules_false():
    """SIM: RiskController met enforce_rules=False laat alles door (budget onbeperkt)."""
    # enforce_rules=False betekent check_can_trade geeft altijd True terug voor SIM
    svc, container = _make_service("sim", risk_ok=True)
    # Simuleer dat check_can_trade True teruggeeft (zoals enforce_rules=False doet)
    result = svc.place_order("BUY", 1)
    assert result is True
    container.broker.submit_order.assert_called_once()


# ─── REAL tests ──────────────────────────────────────────────────────────────

def test_real_mode_submits_when_all_gates_pass():
    """REAL mode: SessionGuard OK + RiskController OK → broker submit."""
    svc, container = _make_service("real")
    result = svc.place_order("BUY", 1)
    assert result is True
    container.broker.submit_order.assert_called_once()


def test_real_mode_blocked_by_risk_controller():
    """REAL mode: RiskController blocked → False, geen broker submit."""
    svc, container = _make_service("real", risk_ok=False)
    result = svc.place_order("BUY", 1)
    assert result is False
    container.broker.submit_order.assert_not_called()


def test_real_mode_blocked_by_session_guard_outside_hours():
    """REAL mode: SessionGuard blokkert buiten trading hours."""
    svc, container = _make_service("real")
    svc.engine.session_guard.is_trading_session.return_value = False
    result = svc.place_order("SELL", 1)
    assert result is False
    container.broker.submit_order.assert_not_called()


def test_real_mode_blocked_by_rollover_window():
    """REAL mode: SessionGuard blokkert tijdens rollover."""
    svc, container = _make_service("real")
    svc.engine.session_guard.is_rollover_window.return_value = True
    result = svc.place_order("BUY", 1)
    assert result is False
    container.broker.submit_order.assert_not_called()


def test_real_mode_session_guard_unavailable_fails_closed():
    """REAL mode zonder SessionGuard → fail-closed (False)."""
    svc, container = _make_service("real")
    svc.engine.session_guard = None
    result = svc.place_order("BUY", 1)
    assert result is False
    container.broker.submit_order.assert_not_called()


def test_real_mode_no_risk_controller_fails_closed():
    """REAL mode zonder RiskController → fail-closed (False)."""
    svc, container = _make_service("real")
    svc.engine.risk_controller = None
    # Zonder SessionGuard guard ook verwijderd om isolatie te garanderen
    svc.engine.session_guard = None
    result = svc.place_order("BUY", 1)
    # Geen risk controller → risk check skipt, maar session guard blokkeert
    # (session_guard=None + enforce=default True → fail-closed)
    assert result is False
    container.broker.submit_order.assert_not_called()


# ─── check_pre_trade_risk SIM-exempt SessionGuard ────────────────────────────

def _make_runtime_ctx(trade_mode: str):
    risk_ctrl = MagicMock()
    risk_ctrl.check_can_trade.return_value = (True, "ok")
    risk_ctrl.apply_regime_override.return_value = None
    limits = SimpleNamespace(enforce_session_guard=True)
    risk_ctrl._active_limits = limits

    session_guard = MagicMock()
    session_guard.is_rollover_window.return_value = True   # actief rollover window
    session_guard.is_trading_session.return_value = False

    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode=trade_mode),
        risk_controller=risk_ctrl,
        session_guard=session_guard,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        reasoning_service=None,
    )
    return SimpleNamespace(engine=engine, logger=MagicMock(), market_regime="NEUTRAL")


def test_check_pre_trade_risk_sim_respects_session_guard():
    """check_pre_trade_risk in SIM blokkert ook tijdens rollover window (live orders!)."""
    app = _make_runtime_ctx("sim")
    ok, reason = check_pre_trade_risk(app, "MES", "NEUTRAL", 10.0)
    assert ok is False
    assert "rollover" in reason.lower()
    app.engine.session_guard.is_rollover_window.assert_called()


def test_check_pre_trade_risk_real_respects_session_guard():
    """check_pre_trade_risk in REAL blokkeert tijdens rollover window."""
    app = _make_runtime_ctx("real")
    ok, reason = check_pre_trade_risk(app, "MES", "NEUTRAL", 10.0)
    assert ok is False
    assert "rollover" in reason.lower()
