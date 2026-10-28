"""S0 D1: confluence / operator / worker places are frozen; flatten still works."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.broker.broker_bridge.schemas import Order, OrderResult
from lumina_core.engine.policy_engine import PolicyEngine
from lumina_core.engine.supervisor_tick_ctx import SupervisorTickCtx
from lumina_core.engine.supervisor_tick_exec import run_tick_exec
from lumina_core.order_gatekeeper.ungated_place_block import (
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    blocked_order_result,
    freeze_is_armed,
    gate_order,
    inspect_order_flags,
    is_risk_reducing_side,
    live_qty_from_order_or_engine,
)
from lumina_core.runtime_context import RuntimeContext
from lumina_core.trade_workers import submit_order_with_risk_check
from tests.test_order_path_regression import _make_service


@pytest.mark.unit
def test_freeze_is_always_armed() -> None:
    assert freeze_is_armed() is True


@pytest.mark.unit
def test_buy_and_sell_without_reduce_only_are_blocked() -> None:
    for side in ("BUY", "SELL"):
        allowed, reason = assert_validation_gate_or_block(
            "supervisor_tick_exec.run_tick_exec",
            order_side=side,
            live_position_qty=0,
        )
        assert allowed is False
        assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_operations_place_order_buy_is_blocked() -> None:
    svc, container = _make_service("sim")
    assert svc.place_order("BUY", 1) is False
    container.broker.submit_order.assert_not_called()


@pytest.mark.unit
def test_policy_execute_order_buy_is_blocked() -> None:
    broker = MagicMock()
    broker.submit_order.return_value = OrderResult(accepted=True, order_id="x", status="filled", message="ok")
    engine = SimpleNamespace(event_bus=None, blackboard=None, live_position_qty=0)
    policy = PolicyEngine(engine=engine, broker=broker)
    result = policy.execute_order(Order(symbol="MES", side="BUY", quantity=1, order_type="MARKET"))
    assert result.accepted is False
    assert result.message == UNGATED_PLACE_BLOCK_REASON
    broker.submit_order.assert_not_called()


@pytest.mark.unit
def test_reduce_only_flatten_reaches_broker() -> None:
    broker = MagicMock()
    broker.submit_order.return_value = OrderResult(accepted=True, order_id="flat", status="filled", message="ok")
    engine = SimpleNamespace(event_bus=None, blackboard=None, live_position_qty=1)
    policy = PolicyEngine(engine=engine, broker=broker)
    order = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        order_type="MARKET",
        metadata={"reduce_only": True, "live_position_qty": 1, "proposed_risk": 1.0, "regime": "NEUTRAL"},
    )
    import lumina_core.engine.policy_engine as pe_mod

    with patch.object(pe_mod, "enforce_pre_trade_gate", return_value=(True, "ok")):
        result = policy.execute_order(order)
    assert result.accepted is True
    broker.submit_order.assert_called_once()


@pytest.mark.unit
def test_emergency_flatten_is_allowed() -> None:
    allowed, reason = assert_validation_gate_or_block(
        "emergency_order_endpoints",
        emergency=True,
        order_side="SELL",
        live_position_qty=2,
        reason="api_emergency_stop",
    )
    assert allowed is True
    assert reason == "emergency_flatten_or_cancel_allowed"


@pytest.mark.unit
def test_submit_order_with_risk_check_buy_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    broker = MagicMock()
    app = SimpleNamespace(
        logger=SimpleNamespace(warning=lambda *_a, **_k: None),
        container=SimpleNamespace(broker=broker),
        engine=SimpleNamespace(config=SimpleNamespace(trade_mode="sim", min_confluence=0.0), live_position_qty=0),
    )
    monkeypatch.setattr(
        "lumina_core.trade_workers.check_pre_trade_risk",
        lambda *_a, **_k: (True, "ok"),
    )
    result = submit_order_with_risk_check(
        cast(RuntimeContext, cast(Any, app)),
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=10.0,
        order=Order(symbol="MES", side="BUY", quantity=1, order_type="MARKET"),
    )
    assert result is None
    broker.submit_order.assert_not_called()


@pytest.mark.unit
def test_supervisor_confluence_does_not_place() -> None:
    place = MagicMock(return_value=True)
    app = SimpleNamespace(
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 2,
        sim_position_qty=0,
        place_order=place,
        open_pnl=0.0,
        account_equity=100.0,
        account_balance=100.0,
        logger=MagicMock(),
    )
    sm = SimpleNamespace(app=app, engine=None, valuation_engine=MagicMock(), _logger=MagicMock())
    ctx = SupervisorTickCtx(
        price=5000.0,
        dream_snapshot={"confluence_score": 0.99, "regime": "TREND", "stop": 4990.0, "target": 5010.0},
        now=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        signal="BUY",
        trade_mode="sim",
        min_confluence=0.5,
    )
    run_tick_exec(sm, ctx)
    place.assert_not_called()


@pytest.mark.unit
def test_supervisor_sell_confluence_does_not_place() -> None:
    place = MagicMock(return_value=True)
    app = SimpleNamespace(
        calculate_adaptive_risk_and_qty=lambda *_a, **_k: 2,
        sim_position_qty=0,
        place_order=place,
        open_pnl=0.0,
        account_equity=100.0,
        account_balance=100.0,
        logger=MagicMock(),
    )
    sm = SimpleNamespace(app=app, engine=None, valuation_engine=MagicMock(), _logger=MagicMock())
    ctx = SupervisorTickCtx(
        price=5000.0,
        dream_snapshot={"confluence_score": 0.99, "regime": "TREND", "stop": 5010.0, "target": 4990.0},
        now=datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc),
        signal="SELL",
        trade_mode="sim",
        min_confluence=0.5,
    )
    run_tick_exec(sm, ctx)
    place.assert_not_called()


@pytest.mark.unit
def test_research_bridge_source_agent_cannot_place() -> None:
    allowed, reason = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        order_side="BUY",
        source_agent="research_bridge",
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_gate_order_without_order_is_blocked() -> None:
    allowed, reason = gate_order("operations_service_orders.place_order", None)
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_blocked_order_result_shape() -> None:
    result = blocked_order_result()
    assert result.accepted is False
    assert result.status == "rejected"
    assert result.message == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_gate_order_reads_metadata() -> None:
    order = Order(
        symbol="MES",
        side="SELL",
        quantity=1,
        metadata={"reduce_only": True, "live_position_qty": 1, "reason": "eod_force_close"},
    )
    allowed, reason = gate_order("eod_force_close", order, emergency=False)
    assert allowed is True
    assert reason == "emergency_flatten_or_cancel_allowed"


@pytest.mark.unit
def test_inspect_and_live_qty_fail_closed_on_bad_metadata() -> None:
    assert inspect_order_flags(None) == (False, "", "")
    odd = SimpleNamespace(side="BUY", metadata="not-a-dict")
    reduce_only, reason, side = inspect_order_flags(cast(Order, odd))
    assert reduce_only is False
    assert reason == ""
    assert side == "BUY"
    bad_qty = Order(symbol="MES", side="SELL", quantity=1, metadata={"live_position_qty": "x"})
    assert live_qty_from_order_or_engine(bad_qty, None, None) == 0
    app = SimpleNamespace(sim_position_qty="nope")
    engine = SimpleNamespace(live_position_qty="nope")
    assert live_qty_from_order_or_engine(None, engine, app) == 0
    assert live_qty_from_order_or_engine(None, None, None) == 0
    assert is_risk_reducing_side(order_side="HOLD", live_position_qty=1) is False
    allowed, blocked = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="HOLD",
        live_position_qty=1,
    )
    assert allowed is False
    assert blocked == UNGATED_PLACE_BLOCK_REASON
