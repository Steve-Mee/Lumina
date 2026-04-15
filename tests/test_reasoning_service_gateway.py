from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.engine.broker_bridge import Order
from lumina_core.engine.reasoning_service import ReasoningService


class _BrokerSpy:
    def __init__(self) -> None:
        self.calls = 0

    def submit_order(self, order: Order):
        self.calls += 1
        return SimpleNamespace(accepted=True, status="FILLED", message="ok", order=order)


def _service(mode: str = "real") -> tuple[ReasoningService, _BrokerSpy]:
    broker = _BrokerSpy()
    engine = SimpleNamespace(
        config=SimpleNamespace(instrument="MES JUN26", min_confluence=0.5, trade_mode=mode),
        app=SimpleNamespace(),
        get_current_dream_snapshot=lambda: {"confluence_score": 0.9, "regime": "NEUTRAL", "hold_until_ts": 0.0},
    )
    service = ReasoningService(
        engine=engine,
        inference_engine=SimpleNamespace(active_provider="ollama"),
        regime_detector=None,
        container=SimpleNamespace(broker=broker),
    )
    return service, broker


def test_reasoning_submit_order_blocks_when_policy_gate_rejects(monkeypatch) -> None:
    service, broker = _service(mode="real")

    monkeypatch.setattr(
        "lumina_core.engine.reasoning_service.enforce_pre_trade_gate",
        lambda *_a, **_k: (False, "Session guard blocked order: outside trading session"),
    )

    with pytest.raises(RuntimeError, match="policy gate blocked"):
        service.submit_order(
            Order(symbol="MES JUN26", side="BUY", quantity=1, order_type="MARKET", stop_loss=4990.0, take_profit=5010.0)
        )

    assert broker.calls == 0


def test_reasoning_submit_order_passes_when_gate_allows(monkeypatch) -> None:
    service, broker = _service(mode="real")

    monkeypatch.setattr(
        "lumina_core.engine.reasoning_service.enforce_pre_trade_gate",
        lambda *_a, **_k: (True, "ok"),
    )

    result = service.submit_order(
        Order(symbol="MES JUN26", side="BUY", quantity=1, order_type="MARKET", stop_loss=4990.0, take_profit=5010.0)
    )

    assert result.accepted is True
    assert broker.calls == 1
