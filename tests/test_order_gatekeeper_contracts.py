from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from lumina_core.order_gatekeeper import enforce_pre_trade_gate, is_stale_contract_symbol


class _RiskController:
    def __init__(self, *, can_trade: bool = True, reason: str = "OK", var_es_ok: bool = True, var_es_reason: str = "VAR_ES OK") -> None:
        self._active_limits = SimpleNamespace(enforce_session_guard=False)
        self._can_trade = bool(can_trade)
        self._reason = str(reason)
        self._var_es_ok = bool(var_es_ok)
        self._var_es_reason = str(var_es_reason)

    def apply_regime_override(self, **_kwargs):
        return None

    def check_can_trade(self, symbol: str, regime: str, proposed_risk: float):
        del symbol, regime, proposed_risk
        return self._can_trade, self._reason

    def check_var_es_pre_trade(self, proposed_risk: float):
        del proposed_risk
        return self._var_es_ok, self._var_es_reason, {}


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


def test_enforce_pre_trade_gate_sim_mode_risk_is_advisory(monkeypatch) -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="sim"),
        risk_controller=_RiskController(can_trade=False, reason="daily_loss_cap"),
        session_guard=None,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        market_regime="NEUTRAL",
        app=SimpleNamespace(logger=SimpleNamespace(warning=lambda *_a, **_k: None)),
    )

    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)
    monkeypatch.setenv("LUMINA_ALLOW_STALE_CONTRACTS", "false")

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
    )

    assert allowed is True
    assert reason == "daily_loss_cap"


def test_enforce_pre_trade_gate_sim_real_guard_blocks_on_risk(monkeypatch) -> None:
    metric_calls: list[tuple[str, str]] = []

    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="sim_real_guard"),
        risk_controller=_RiskController(can_trade=False, reason="daily_loss_cap"),
        session_guard=None,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        market_regime="NEUTRAL",
        observability_service=SimpleNamespace(
            record_mode_guard_block=lambda *, mode, reason: metric_calls.append((str(mode), str(reason)))
        ),
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
    assert reason == "daily_loss_cap"
    assert metric_calls == [("sim_real_guard", "risk_daily_loss_cap")]


def test_enforce_pre_trade_gate_real_blocks_on_var_es(monkeypatch) -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real"),
        risk_controller=_RiskController(var_es_ok=False, var_es_reason="VAR_ES breached: VaR95 1400 > 1200"),
        session_guard=None,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        market_regime="NEUTRAL",
        observability_service=SimpleNamespace(record_mode_guard_block=lambda **_kwargs: None),
    )

    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
    )

    assert allowed is False
    assert "VAR_ES breached" in reason


def test_enforce_pre_trade_gate_sim_var_es_is_advisory(monkeypatch) -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="sim"),
        risk_controller=_RiskController(var_es_ok=False, var_es_reason="VAR_ES breached: ES95 1600 > 1500"),
        session_guard=None,
        current_regime_snapshot={"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        market_regime="NEUTRAL",
        app=SimpleNamespace(logger=SimpleNamespace(warning=lambda *_a, **_k: None)),
    )

    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
    )

    assert allowed is True
    assert reason == "OK"
