from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from lumina_core.order_gatekeeper import enforce_pre_trade_gate, is_stale_contract_symbol


class _RiskController:
    def __init__(
        self,
        *,
        can_trade: bool = True,
        reason: str = "OK",
        var_es_ok: bool = True,
        var_es_reason: str = "VAR_ES OK",
        mc_ok: bool = True,
        mc_reason: str = "MC drawdown OK",
    ) -> None:
        self._active_limits = SimpleNamespace(enforce_session_guard=False)
        self._can_trade = bool(can_trade)
        self._reason = str(reason)
        self._var_es_ok = bool(var_es_ok)
        self._var_es_reason = str(var_es_reason)
        self._mc_ok = bool(mc_ok)
        self._mc_reason = str(mc_reason)

    def apply_regime_override(self, **_kwargs):
        return None

    def check_can_trade(self, symbol: str, regime: str, proposed_risk: float):
        del symbol, regime, proposed_risk
        return self._can_trade, self._reason

    def check_var_es_pre_trade(self, proposed_risk: float):
        del proposed_risk
        return self._var_es_ok, self._var_es_reason, {}

    def check_monte_carlo_drawdown_pre_trade(self, proposed_risk: float):
        del proposed_risk
        return self._mc_ok, self._mc_reason, {}

    def record_regime_snapshot(self, _snapshot):
        return None


class _BrokerWithMetadata:
    def __init__(self, tradeable: bool, reason: str = "") -> None:
        self._tradeable = bool(tradeable)
        self._reason = str(reason or "")

    def is_contract_tradeable(self, symbol: str):
        del symbol
        return self._tradeable, self._reason


class _Event:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.producer = "test-agent"
        self.confidence = 0.8
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.correlation_id = "corr-1"
        self.sequence = 1
        self.event_hash = "event-hash"
        self.prev_hash = "prev-hash"


class _Blackboard:
    def latest(self, topic: str):
        if topic in {
            "agent.rl.proposal",
            "agent.news.proposal",
            "agent.emotional_twin.proposal",
            "agent.swarm.proposal",
            "agent.tape.proposal",
        }:
            return _Event({"agent_id": "rl", "confidence": 0.81, "reason": "test"})
        if topic == "execution.aggregate":
            return _Event({"signal": "BUY", "chosen_strategy": "rl"})
        return None


def _make_engine(
    *,
    trade_mode: str,
    risk_controller: _RiskController,
    **overrides,
) -> SimpleNamespace:
    defaults = {
        "config": SimpleNamespace(trade_mode=trade_mode),
        "risk_controller": risk_controller,
        "session_guard": None,
        "current_regime_snapshot": {"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}},
        "market_regime": "NEUTRAL",
        "reasoning_service": SimpleNamespace(refresh_regime_snapshot=lambda: {"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}}),
        "get_current_dream_snapshot": lambda: {"confidence": 0.7, "expected_value": 1.2},
        "blackboard": _Blackboard(),
        "audit_log_service": SimpleNamespace(log_decision=lambda *_args, **_kwargs: True),
        "app": SimpleNamespace(logger=SimpleNamespace(warning=lambda *_a, **_k: None)),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_is_stale_contract_symbol_detects_expired_month() -> None:
    assert is_stale_contract_symbol("MES JAN24", now_utc=datetime(2026, 4, 15, tzinfo=timezone.utc)) is True


def test_is_stale_contract_symbol_allows_current_or_future_month() -> None:
    assert is_stale_contract_symbol("MES JUN26", now_utc=datetime(2026, 4, 15, tzinfo=timezone.utc)) is False
    assert is_stale_contract_symbol("MES DEC27", now_utc=datetime(2026, 4, 15, tzinfo=timezone.utc)) is False


def test_enforce_pre_trade_gate_blocks_stale_contract_in_sim_mode(monkeypatch) -> None:
    engine = _make_engine(trade_mode="sim", risk_controller=_RiskController())

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
    engine = _make_engine(trade_mode="real", risk_controller=_RiskController())

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
    engine = _make_engine(
        trade_mode="real",
        risk_controller=_RiskController(),
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
    engine = _make_engine(trade_mode="sim", risk_controller=_RiskController(can_trade=False, reason="daily_loss_cap"))

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

    engine = _make_engine(
        trade_mode="sim_real_guard",
        risk_controller=_RiskController(can_trade=False, reason="daily_loss_cap"),
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
    engine = _make_engine(
        trade_mode="real",
        risk_controller=_RiskController(var_es_ok=False, var_es_reason="VAR_ES breached: VaR95 1400 > 1200"),
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
    engine = _make_engine(trade_mode="sim", risk_controller=_RiskController(var_es_ok=False, var_es_reason="VAR_ES breached: ES95 1600 > 1500"))

    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
    )

    assert allowed is True
    assert reason == "OK"


def test_enforce_pre_trade_gate_real_blocks_on_mc_drawdown(monkeypatch) -> None:
    engine = _make_engine(
        trade_mode="real",
        risk_controller=_RiskController(mc_ok=False, mc_reason="MC projected max drawdown 13.5% > threshold 12.0%"),
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
    assert "drawdown" in reason.lower()


def test_enforce_pre_trade_gate_real_fail_closed_when_audit_write_fails(monkeypatch) -> None:
    engine = _make_engine(
        trade_mode="real",
        risk_controller=_RiskController(),
        observability_service=SimpleNamespace(record_mode_guard_block=lambda **_kwargs: None),
        audit_log_service=SimpleNamespace(log_decision=lambda *_args, **_kwargs: False),
    )

    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
    )

    assert allowed is False
    assert "audit fail-closed" in reason.lower()
