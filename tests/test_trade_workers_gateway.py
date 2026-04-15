from __future__ import annotations

from types import SimpleNamespace

from lumina_core.engine.broker_bridge import Order
from lumina_core.trade_workers import submit_order_with_risk_check


class _BrokerSpy:
    def __init__(self) -> None:
        self.calls = 0

    def submit_order(self, order: Order):
        self.calls += 1
        return SimpleNamespace(accepted=True, status="FILLED", message="ok", order=order)


def _app(mode: str = "real"):
    broker = _BrokerSpy()
    app = SimpleNamespace(
        logger=SimpleNamespace(warning=lambda *_a, **_k: None),
        container=SimpleNamespace(broker=broker),
        engine=SimpleNamespace(config=SimpleNamespace(trade_mode=mode, min_confluence=0.5)),
    )
    return app, broker


def test_submit_order_with_risk_check_blocks_when_pre_trade_fails(monkeypatch) -> None:
    app, broker = _app("real")

    monkeypatch.setattr(
        "lumina_core.trade_workers.check_pre_trade_risk",
        lambda *_a, **_k: (False, "blocked"),
    )

    result = submit_order_with_risk_check(
        app,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=100.0,
        order=Order(symbol="MES JUN26", side="BUY", quantity=1, order_type="MARKET", stop_loss=4990.0, take_profit=5010.0),
    )

    assert result is None
    assert broker.calls == 0


def test_submit_order_with_risk_check_submits_when_allowed(monkeypatch) -> None:
    app, broker = _app("real")

    monkeypatch.setattr(
        "lumina_core.trade_workers.check_pre_trade_risk",
        lambda *_a, **_k: (True, "ok"),
    )

    result = submit_order_with_risk_check(
        app,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=100.0,
        order=Order(symbol="MES JUN26", side="BUY", quantity=1, order_type="MARKET", stop_loss=4990.0, take_profit=5010.0),
    )

    assert result is not None
    assert result.accepted is True
    assert broker.calls == 1
