from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from lumina_core.order_gatekeeper import enforce_pre_trade_gate, is_stale_contract_symbol


class _RiskController:
    def __init__(self) -> None:
        self._active_limits = SimpleNamespace(enforce_session_guard=False)

    def apply_regime_override(self, **_kwargs):
        return None

    def check_can_trade(self, symbol: str, regime: str, proposed_risk: float):
        del symbol, regime, proposed_risk
        return True, "OK"


class _BrokerWithMetadata:
    def __init__(self, tradeable: bool, reason: str = "") -> None:
        self._tradeable = bool(tradeable)
        self._reason = str(reason or "")

    def is_contract_tradeable(self, symbol: str):
        del symbol
        return self._tradeable, self._reason


def test_is_stale_contract_symbol_detects_expired_month() -> None:
    assert is_stale_contract_symbol("MES JAN24", now_utc=datetime(2026, 4, 15, tzinfo=timezone.utc)) is True


def test_is_stale_contract_symbol_allows_current_or_future_month() -> None:
    assert is_stale_contract_symbol("MES JUN26", now_utc=datetime(2026, 4, 15, tzinfo=timezone.utc)) is False
    assert is_stale_contract_symbol("MES DEC27", now_utc=datetime(2026, 4, 15, tzinfo=timezone.utc)) is False


def test_enforce_pre_trade_gate_blocks_stale_contract_in_sim_mode(monkeypatch) -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="sim"),
        risk_controller=_RiskController(),
        session_guard=None,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        market_regime="NEUTRAL",
    )

    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: True)
    monkeypatch.setenv("LUMINA_ALLOW_STALE_CONTRACTS", "false")

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JAN24",
        regime="NEUTRAL",
        proposed_risk=50.0,
    )

    assert allowed is False
    assert "stale/expired" in reason


def test_enforce_pre_trade_gate_allows_override_for_stale_contract(monkeypatch) -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real"),
        risk_controller=_RiskController(),
        session_guard=None,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        market_regime="NEUTRAL",
    )

    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: True)
    monkeypatch.setenv("LUMINA_ALLOW_STALE_CONTRACTS", "true")

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JAN24",
        regime="NEUTRAL",
        proposed_risk=50.0,
    )

    assert allowed is True
    assert reason == "OK"


def test_enforce_pre_trade_gate_blocks_when_broker_metadata_rejects_symbol(monkeypatch) -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real"),
        risk_controller=_RiskController(),
        session_guard=None,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        market_regime="NEUTRAL",
        container=SimpleNamespace(broker=_BrokerWithMetadata(False, "expired_by_exchange")),
    )

    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)
    monkeypatch.setenv("LUMINA_ALLOW_STALE_CONTRACTS", "false")

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
    )

    assert allowed is False
    assert "broker metadata" in reason.lower()
