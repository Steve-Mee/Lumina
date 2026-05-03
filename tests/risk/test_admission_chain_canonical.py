from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Callable

import pytest

from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.risk.admission_chain import (
    ADMISSION_STEP_AUDIT_WRITE,
    ADMISSION_STEP_CONSTITUTION,
    ADMISSION_STEP_FINAL_ARBITRATION,
    ADMISSION_STEP_RISK_POLICY,
    ADMISSION_STEP_SESSION_EQUITY_SYNC,
    CANONICAL_ADMISSION_STEPS,
    default_chain_for_mode,
)


class _Event:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.producer = "test-agent"
        self.confidence = 0.81
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.correlation_id = "corr-1"
        self.sequence = 1
        self.event_hash = "event-hash"
        self.prev_hash = "prev-hash"


class _Blackboard:
    def latest(self, topic: str) -> _Event | None:
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


class _RiskController:
    def __init__(self) -> None:
        self._active_limits = SimpleNamespace(enforce_session_guard=False)
        self._can_trade = True
        self._reason = "OK"
        self._var_es_ok = True
        self._var_es_reason = "VAR_ES OK"
        self._mc_ok = True
        self._mc_reason = "MC drawdown OK"
        self.state = SimpleNamespace(
            open_risk_by_symbol={},
            margin_tracker=SimpleNamespace(account_equity=50_000.0),
            var_95_usd=0.0,
            var_99_usd=0.0,
            es_95_usd=0.0,
            es_99_usd=0.0,
        )

    def apply_regime_override(self, **_kwargs) -> None:
        return None

    def check_can_trade(self, _symbol: str, _regime: str, _proposed_risk: float) -> tuple[bool, str]:
        return bool(self._can_trade), str(self._reason)

    def check_var_es_pre_trade(self, _proposed_risk: float) -> tuple[bool, str, dict[str, Any]]:
        return bool(self._var_es_ok), str(self._var_es_reason), {}

    def check_monte_carlo_drawdown_pre_trade(self, _proposed_risk: float) -> tuple[bool, str, dict[str, Any]]:
        return bool(self._mc_ok), str(self._mc_reason), {}

    def record_regime_snapshot(self, _snapshot: dict[str, Any]) -> None:
        return None


class _FinalArbitration:
    def __init__(self, *, approved: bool = True, reason: str = "approved") -> None:
        self.approved = bool(approved)
        self.reason = str(reason)
        self.last_skip_internal_steps: frozenset[str] = frozenset()

    def check_order_intent(self, *_args, skip_internal_steps: frozenset[str] | None = None, **_kwargs):
        self.last_skip_internal_steps = frozenset(skip_internal_steps or frozenset())
        status = "APPROVED" if self.approved else "REJECTED"
        return SimpleNamespace(status=status, reason=self.reason)


def _fresh_snapshot() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        is_fresh=True,
        source="unit-test-provider",
        reason_code="ok_live",
        equity_usd=50_000.0,
        available_margin_usd=45_000.0,
        used_margin_usd=5_000.0,
    )


def _make_engine(*, trade_mode: str = "real") -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(trade_mode=trade_mode, instrument="MES JUN26"),
        risk_controller=_RiskController(),
        session_guard=None,
        reasoning_service=SimpleNamespace(
            refresh_regime_snapshot=lambda: {"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}}
        ),
        get_current_dream_snapshot=lambda: {"confidence": 0.8, "expected_value": 1.2, "regime": "NEUTRAL"},
        blackboard=_Blackboard(),
        audit_log_service=SimpleNamespace(log_decision=lambda *_args, **_kwargs: True),
        app=SimpleNamespace(logger=SimpleNamespace(warning=lambda *_a, **_k: None)),
        equity_snapshot_provider=SimpleNamespace(get_snapshot=lambda: _fresh_snapshot()),
        account_equity=50_000.0,
        available_margin=45_000.0,
        positions_margin_used=5_000.0,
        live_position_qty=0,
        final_arbitration=_FinalArbitration(),
    )


def _block_session_sync(engine: SimpleNamespace, _monkeypatch: pytest.MonkeyPatch) -> None:
    engine.risk_controller._active_limits.enforce_session_guard = True
    engine.session_guard = SimpleNamespace(
        is_rollover_window=lambda: False,
        is_trading_session=lambda: False,
        next_open=lambda: datetime(2026, 5, 4, 13, 0, tzinfo=timezone.utc),
    )


@pytest.fixture(autouse=True)
def _default_constitution_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.order_gatekeeper.evaluate_constitution_for_intent",
        lambda **_kwargs: (True, "constitution_ok"),
    )


@pytest.mark.unit
def test_default_chain_uses_canonical_sequence() -> None:
    assert tuple(default_chain_for_mode("real").steps) == CANONICAL_ADMISSION_STEPS


@pytest.mark.unit
def test_enforce_pre_trade_gate_success_trace_is_canonical() -> None:
    engine = _make_engine(trade_mode="real")
    final_arbitration = engine.final_arbitration

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        order_side="BUY",
    )

    assert allowed is True
    assert reason == "OK"
    assert [step["step_id"] for step in engine.admission_chain_trace] == list(CANONICAL_ADMISSION_STEPS)
    assert engine.admission_chain_final_arbitration_approved is True
    assert final_arbitration.last_skip_internal_steps == frozenset(
        {"real_equity_snapshot", "risk_policy", "constitution"}
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("step_id", "mutate_engine", "reason_fragment"),
    [
        (
            ADMISSION_STEP_SESSION_EQUITY_SYNC,
            _block_session_sync,
            "session guard blocked",
        ),
        (
            ADMISSION_STEP_RISK_POLICY,
            lambda engine, _monkeypatch: setattr(engine.risk_controller, "_var_es_ok", False),
            "var_es",
        ),
        (
            ADMISSION_STEP_FINAL_ARBITRATION,
            lambda engine, _monkeypatch: setattr(
                engine, "final_arbitration", _FinalArbitration(approved=False, reason="final_arb_block")
            ),
            "final_arb_block",
        ),
        (
            ADMISSION_STEP_CONSTITUTION,
            lambda _engine, monkeypatch: monkeypatch.setattr(
                "lumina_core.order_gatekeeper.evaluate_constitution_for_intent",
                lambda **_kwargs: (False, "constitution_block"),
            ),
            "constitution_block",
        ),
        (
            ADMISSION_STEP_AUDIT_WRITE,
            lambda engine, _monkeypatch: setattr(
                engine, "audit_log_service", SimpleNamespace(log_decision=lambda *_a, **_k: False)
            ),
            "audit fail-closed",
        ),
    ],
)
def test_enforce_pre_trade_gate_blocks_at_each_canonical_step(
    step_id: str,
    mutate_engine: Callable[[SimpleNamespace, pytest.MonkeyPatch], Any],
    reason_fragment: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _make_engine(trade_mode="real")
    mutate_engine(engine, monkeypatch)

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        order_side="BUY",
    )

    assert allowed is False
    assert reason_fragment.lower() in str(reason).lower()
    assert engine.admission_chain_trace[-1]["step_id"] == step_id
