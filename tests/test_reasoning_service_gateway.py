from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, cast

import pytest

from lumina_core.broker.broker_bridge import Order
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.reasoning.local_inference_engine import LocalInferenceEngine
from lumina_core.reasoning.reasoning_service import ReasoningDecisionLogError, ReasoningService
from lumina_core.risk.equity_snapshot import EquitySnapshot


class _BrokerSpy:
    def __init__(self) -> None:
        self.calls = 0

    def submit_order(self, order: Order):
        self.calls += 1
        return SimpleNamespace(accepted=True, status="FILLED", message="ok", order=order)


class _FailingDecisionLog:
    def log_decision(self, **_: Any) -> None:
        raise RuntimeError("decision log down")


def _service(mode: str = "real") -> tuple[ReasoningService, _BrokerSpy]:
    broker = _BrokerSpy()

    class _SnapshotProvider:
        def get_snapshot(self) -> EquitySnapshot:
            return EquitySnapshot(
                equity_usd=100_000.0,
                available_margin_usd=60_000.0,
                used_margin_usd=40_000.0,
                as_of_utc=datetime.now(timezone.utc),
                source="test",
                ok=True,
                reason_code="ok_live",
                ttl_seconds=30.0,
            )

    engine = SimpleNamespace(
        config=SimpleNamespace(instrument="MES JUN26", min_confluence=0.5, trade_mode=mode),
        app=SimpleNamespace(
            account_equity=100_000.0,
            available_margin=50_000.0,
            positions_margin_used=0.0,
            realized_pnl_today=0.0,
            sim_position_qty=0,
        ),
        get_current_dream_snapshot=lambda: {"confluence_score": 0.9, "regime": "NEUTRAL", "hold_until_ts": 0.0},
        equity_snapshot_provider=_SnapshotProvider(),
        risk_controller=None,
        realized_pnl_today=0.0,
        account_equity=100_000.0,
        available_margin=50_000.0,
        positions_margin_used=0.0,
        drawdown_pct=0.0,
        live_position_qty=0,
    )
    inference_engine = SimpleNamespace(active_provider="ollama")
    service = ReasoningService(
        engine=cast(LuminaEngine, cast(Any, engine)),
        inference_engine=cast(LocalInferenceEngine, cast(Any, inference_engine)),
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
    monkeypatch.setattr(
        "lumina_core.engine.policy_engine.enforce_pre_trade_gate",
        lambda *_a, **_k: (True, "ok"),
    )

    result = service.submit_order(
        Order(symbol="MES JUN26", side="BUY", quantity=1, order_type="MARKET", stop_loss=4990.0, take_profit=5010.0)
    )

    assert result.accepted is True
    assert broker.calls == 1


def test_reasoning_decision_log_fail_closed_in_real_mode() -> None:
    service, _broker = _service(mode="real")
    service.engine.decision_log = _FailingDecisionLog()

    with pytest.raises(ReasoningDecisionLogError):
        service._log_decision(
            agent_id="ReasoningService",
            raw_input={"signal": "BUY"},
            raw_output={"signal": "BUY", "approved": True},
            confidence=0.8,
            policy_outcome="accepted",
            decision_context_id="ctx-real-fail",
            model_version="test-model",
        )
