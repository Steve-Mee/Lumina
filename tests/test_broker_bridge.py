from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, cast

from lumina_core.engine.broker_bridge import (
    CrossTradeBroker,
    Order,
    OrderResult,
    PaperBroker,
    broker_factory,
)
from lumina_core.engine.operations_service import OperationsService


class _Event:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.producer = "test"
        self.confidence = float(payload.get("confidence", 0.8) or 0.8)
        self.timestamp = "2026-04-18T00:00:00+00:00"
        self.correlation_id = "corr"
        self.sequence = 1
        self.event_hash = "hash"
        self.prev_hash = "prev-hash"


class _Blackboard:
    def latest(self, topic: str):
        if topic.startswith("agent."):
            return _Event({"agent_id": "rl", "signal": "BUY", "confidence": 0.81, "reason": "test"})
        if topic == "execution.aggregate":
            return _Event({"signal": "BUY", "chosen_strategy": "rl"})
        return None


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | list | None = None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.content = b"{}"

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self):
        self.calls: list[tuple[str, str, dict | None, dict | None]] = []

    def post(self, url: str, headers=None, json=None, timeout: float = 0):
        self.calls.append(("POST", url, headers, json))
        payload = json if isinstance(json, dict) else {}
        return _FakeResponse(
            201, {"orderId": "order-123", "filledQuantity": payload.get("quantity", 0), "fillPrice": 5001.25}
        )

    def get(self, url: str, headers=None, timeout: float = 0):
        self.calls.append(("GET", url, headers, None))
        if url.endswith("/positions"):
            return _FakeResponse(200, [{"instrument": "MES JUN26", "quantity": 1, "avgPrice": 5000.0}])
        return _FakeResponse(200, {"balance": 50250.0, "equity": 50310.0, "realizedPnlToday": 42.0})

    def close(self):
        return None


def test_broker_factory_selects_paper() -> None:
    cfg = SimpleNamespace(broker_backend="paper")
    broker = broker_factory(config=cfg, engine=None, logger=None)
    assert isinstance(broker, PaperBroker)


def test_paper_broker_submit_order_and_fill_tracking() -> None:
    engine = SimpleNamespace(
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.5}],
        ohlc_1min=[],
        account_balance=50000.0,
        account_equity=50000.0,
        realized_pnl_today=0.0,
    )
    broker = PaperBroker(engine=engine)

    result = broker.submit_order(
        Order(symbol="MES JUN26", side="BUY", quantity=2, stop_loss=4995.0, take_profit=5010.0)
    )

    assert result.accepted is True
    assert result.status == "filled"
    assert result.filled_qty == 2
    assert len(broker.get_positions()) == 1
    fills = broker.get_fills()
    assert len(fills) == 1
    assert fills[0].symbol == "MES JUN26"


def test_cross_trade_broker_and_operations_service_submit_via_bridge() -> None:
    fake_session = _FakeSession()
    broker = CrossTradeBroker(
        api_key="test-token",
        account="DEMO123",
        websocket_url="wss://example/ws",
        base_url="https://example",
    )
    broker._session = cast(Any, fake_session)  # test seam

    direct = broker.submit_order(
        Order(symbol="MES JUN26", side="SELL", quantity=1, stop_loss=5010.0, take_profit=4990.0)
    )
    assert direct.accepted is True
    assert direct.order_id == "order-123"

    class _BrokerSpy:
        def __init__(self):
            self.calls: list[Order] = []

        def submit_order(self, order: Order) -> OrderResult:
            self.calls.append(order)
            return OrderResult(accepted=True, order_id="spy-1", status="accepted", filled_qty=order.quantity)

        def get_account_info(self):
            return SimpleNamespace(balance=50000.0, equity=50020.0, realized_pnl_today=5.0)

    broker_spy = _BrokerSpy()
    container = SimpleNamespace(broker=broker_spy)

    engine = SimpleNamespace(
        app=SimpleNamespace(
            logger=SimpleNamespace(
                error=lambda *a, **k: None,
                info=lambda *a, **k: None,
                warning=lambda *a, **k: None,
            )
        ),
        config=SimpleNamespace(trade_mode="real", instrument="MES JUN26"),
        get_current_dream_snapshot=lambda: {"stop": 4990.0, "target": 5010.0, "regime": "NEUTRAL"},
        reasoning_service=SimpleNamespace(
            refresh_regime_snapshot=lambda: {"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}}
        ),
        blackboard=_Blackboard(),
        audit_log_service=SimpleNamespace(log_decision=lambda *_a, **_k: True),
        risk_controller=SimpleNamespace(
            _active_limits=SimpleNamespace(enforce_session_guard=True),
            apply_regime_override=lambda *_a, **_k: None,
            check_can_trade=lambda *_a, **_k: (True, "ok"),
            check_var_es_pre_trade=lambda *_a, **_k: (True, "VAR_ES OK", {}),
            check_monte_carlo_drawdown_pre_trade=lambda *_a, **_k: (True, "MC drawdown OK", {}),
        ),
        session_guard=SimpleNamespace(
            is_rollover_window=lambda: False,
            is_trading_session=lambda: True,
        ),
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=[1],
        valuation_engine=SimpleNamespace(),
        account_balance=50000.0,
        account_equity=50000.0,
        realized_pnl_today=0.0,
        live_position_qty=0,
        last_entry_price=0.0,
        live_trade_signal="HOLD",
        last_realized_pnl_snapshot=0.0,
    )

    service = OperationsService(cast(Any, engine), container)
    ok = service.place_order("BUY", 3)

    assert ok is True
    assert len(broker_spy.calls) == 1
    submitted = broker_spy.calls[0]
    assert submitted.symbol == "MES JUN26"
    assert submitted.quantity == 3
