from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, cast

from lumina_core.broker.broker_bridge import (
    CrossTradeBroker,
    Order,
    OrderResult,
    PaperBroker,
    broker_factory,
)
from lumina_core.engine.operations_service import OperationsService
from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_policy import RiskPolicy


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


class _FreshEquitySnapshotProvider:
    def get_snapshot(self):
        return SimpleNamespace(
            ok=True,
            is_fresh=True,
            reason_code="ok",
            source="test_provider",
            equity_usd=50_000.0,
            available_margin_usd=40_000.0,
            used_margin_usd=10_000.0,
            age_seconds=0.2,
        )


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


def _real_policy() -> RiskPolicy:
    return RiskPolicy(
        runtime_mode="real",
        daily_loss_cap=-1000.0,
        max_open_risk_per_instrument=500.0,
        max_total_open_risk=1200.0,
        max_exposure_per_regime=2000.0,
        var_95_limit_usd=1200.0,
        var_99_limit_usd=1800.0,
        es_95_limit_usd=1500.0,
        es_99_limit_usd=2200.0,
        margin_min_confidence=0.6,
    )


def _policy_for_mode(mode: str) -> RiskPolicy:
    policy = _real_policy()
    policy.runtime_mode = str(mode)
    return policy


def test_broker_factory_selects_paper() -> None:
    cfg = SimpleNamespace(broker_backend="paper")
    broker = broker_factory(config=cfg, engine=None, logger=None)
    assert isinstance(broker, PaperBroker)


def test_broker_factory_live_allows_sim() -> None:
    cfg = SimpleNamespace(
        broker_backend="live",
        trade_mode="sim",
        crosstrade_token="test-token",
        crosstrade_account="DEMO5042070",
    )
    broker = broker_factory(config=cfg, engine=None, logger=None)
    assert isinstance(broker, CrossTradeBroker)


def test_paper_broker_submit_order_and_fill_tracking() -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="paper"),
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.5}],
        ohlc_1min=[],
        account_balance=50000.0,
        account_equity=50000.0,
        available_margin=45000.0,
        positions_margin_used=5000.0,
        realized_pnl_today=0.0,
        risk_controller=SimpleNamespace(
            state=SimpleNamespace(open_risk_by_symbol={}, margin_tracker=SimpleNamespace(account_equity=50000.0))
        ),
        get_current_dream_snapshot=lambda: {"regime": "NEUTRAL"},
        equity_snapshot_provider=_FreshEquitySnapshotProvider(),
        final_arbitration=FinalArbitration(
            RiskPolicy(
                runtime_mode="paper",
                daily_loss_cap=-1000.0,
                max_open_risk_per_instrument=500.0,
                max_total_open_risk=3000.0,
                max_exposure_per_regime=2000.0,
                var_95_limit_usd=1200.0,
                var_99_limit_usd=1800.0,
                es_95_limit_usd=1500.0,
                es_99_limit_usd=2200.0,
                margin_min_confidence=0.6,
            )
        ),
    )
    broker = PaperBroker(engine=engine)

    result = broker.submit_order(
        Order(
            symbol="MES JUN26",
            side="BUY",
            quantity=2,
            stop_loss=4995.0,
            take_profit=5010.0,
            metadata={"skip_admission_chain_recheck": True},
        )
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
    broker.engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="sim"),
        risk_policy=_policy_for_mode("sim"),
        risk_controller=SimpleNamespace(
            state=SimpleNamespace(
                open_risk_by_symbol={},
                margin_tracker=SimpleNamespace(account_equity=50_000.0),
                var_95_usd=0.0,
                var_99_usd=0.0,
                es_95_usd=0.0,
                es_99_usd=0.0,
            )
        ),
        get_current_dream_snapshot=lambda: {"regime": "NEUTRAL"},
        account_equity=50_000.0,
        available_margin=40_000.0,
        positions_margin_used=10_000.0,
        realized_pnl_today=0.0,
        drawdown_pct=0.0,
        live_position_qty=0,
        final_arbitration=FinalArbitration(_policy_for_mode("sim")),
    )
    broker._session = cast(Any, fake_session)  # test seam

    direct = broker.submit_order(
        Order(
            symbol="MES JUN26",
            side="SELL",
            quantity=1,
            stop_loss=5010.0,
            take_profit=4990.0,
            metadata={"skip_admission_chain_recheck": True},
        )
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
        equity_snapshot_provider=_FreshEquitySnapshotProvider(),
        final_arbitration=FinalArbitration(_real_policy()),
    )

    service = OperationsService(cast(Any, engine), container)
    ok = service.place_order("BUY", 3)

    assert ok is True
    assert len(broker_spy.calls) == 1
    submitted = broker_spy.calls[0]
    assert submitted.symbol == "MES JUN26"
    assert submitted.quantity == 3


def test_paper_broker_rejects_when_engine_missing() -> None:
    broker = PaperBroker(engine=None)
    result = broker.submit_order(Order(symbol="MES JUN26", side="BUY", quantity=1))
    assert result.accepted is False
    assert result.status == "rejected"
    assert "admission_engine_required" in result.message


def test_operations_service_blocks_real_without_final_arbitration() -> None:
    class _BrokerSpy:
        def __init__(self):
            self.calls = 0

        def submit_order(self, order: Order) -> OrderResult:
            self.calls += 1
            return OrderResult(accepted=True, order_id="spy-1", status="accepted", filled_qty=order.quantity)

        def get_account_info(self):
            return SimpleNamespace(balance=50000.0, equity=50020.0, realized_pnl_today=5.0)

    broker_spy = _BrokerSpy()
    container = SimpleNamespace(broker=broker_spy)
    engine = SimpleNamespace(
        app=SimpleNamespace(
            logger=SimpleNamespace(error=lambda *a, **k: None, info=lambda *a, **k: None, warning=lambda *a, **k: None)
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
            state=SimpleNamespace(open_risk_by_symbol={}, margin_tracker=SimpleNamespace(account_equity=50000.0)),
            apply_regime_override=lambda *_a, **_k: None,
            check_can_trade=lambda *_a, **_k: (True, "ok"),
            check_var_es_pre_trade=lambda *_a, **_k: (True, "VAR_ES OK", {}),
            check_monte_carlo_drawdown_pre_trade=lambda *_a, **_k: (True, "MC drawdown OK", {}),
        ),
        session_guard=SimpleNamespace(is_rollover_window=lambda: False, is_trading_session=lambda: True),
        live_data_lock=nullcontext(),
        live_quotes=[{"last": 5000.0}],
        ohlc_1min=[1],
        valuation_engine=SimpleNamespace(),
        account_balance=50000.0,
        account_equity=50000.0,
        available_margin=45000.0,
        positions_margin_used=5000.0,
        realized_pnl_today=0.0,
        live_position_qty=0,
        last_entry_price=0.0,
        live_trade_signal="HOLD",
        last_realized_pnl_snapshot=0.0,
        equity_snapshot_provider=_FreshEquitySnapshotProvider(),
        final_arbitration=None,
    )
    service = OperationsService(cast(Any, engine), container)
    ok = service.place_order("BUY", 1)
    assert ok is False
    assert broker_spy.calls == 0
