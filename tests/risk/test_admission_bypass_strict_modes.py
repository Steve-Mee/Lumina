"""SC-1: LUMINA_ADMISSION_BYPASS_STEPS must fail-closed in risk-enforced modes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.agent_orchestration.schemas import TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
from lumina_core.engine.mode_capabilities import resolve_mode_capabilities
from lumina_core.order_gatekeeper import enforce_pre_trade_gate
from lumina_core.risk.admission_chain import ADMISSION_STEP_CONSTITUTION


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
        return None


class _EbExec:
    def __init__(self) -> None:
        self.payload: dict[str, object] = {"signal": "BUY", "chosen_strategy": "rl", "confidence": 0.81}
        self.producer = "test-agent"
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.metadata = {"sequence": 1, "correlation_id": "corr-1"}

    def to_dict(self) -> dict[str, object]:
        return {
            "topic": TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
            "producer": self.producer,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class _EventBus:
    def latest(self, topic: str) -> _EbExec | None:
        if topic == TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC:
            return _EbExec()
        return None


class _RiskController:
    def __init__(self) -> None:
        self._active_limits = SimpleNamespace(enforce_session_guard=False)
        self.state = SimpleNamespace(
            open_risk_by_symbol={},
            margin_tracker=SimpleNamespace(account_equity=50_000.0),
            var_95_usd=0.0,
            var_99_usd=0.0,
            es_95_usd=0.0,
            es_99_usd=0.0,
        )

    def apply_regime_override(self, **_kwargs: Any) -> None:
        return None

    def check_can_trade(self, _symbol: str, _regime: str, _proposed_risk: float) -> tuple[bool, str]:
        return True, "OK"

    def check_var_es_pre_trade(self, _proposed_risk: float) -> tuple[bool, str, dict[str, Any]]:
        return True, "VAR_ES OK", {}

    def check_monte_carlo_drawdown_pre_trade(self, _proposed_risk: float) -> tuple[bool, str, dict[str, Any]]:
        return True, "MC drawdown OK", {}

    def record_regime_snapshot(self, _snapshot: dict[str, Any]) -> None:
        return None


class _FinalArbitration:
    def check_order_intent(self, *_args: Any, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(status="APPROVED", reason="approved")


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


def _make_engine(*, trade_mode: str) -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(trade_mode=trade_mode, instrument="MES JUN26"),
        risk_controller=_RiskController(),
        session_guard=None,
        reasoning_service=SimpleNamespace(
            refresh_regime_snapshot=lambda: {"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}}
        ),
        get_current_dream_snapshot=lambda: {"confidence": 0.8, "expected_value": 1.2, "regime": "NEUTRAL"},
        blackboard=_Blackboard(),
        event_bus=_EventBus(),
        audit_log_service=SimpleNamespace(log_decision=lambda *_args, **_kwargs: True),
        app=SimpleNamespace(logger=SimpleNamespace(warning=lambda *_a, **_k: None)),
        equity_snapshot_provider=SimpleNamespace(get_snapshot=lambda: _fresh_snapshot()),
        account_equity=50_000.0,
        available_margin=45_000.0,
        positions_margin_used=5_000.0,
        live_position_qty=0,
        final_arbitration=_FinalArbitration(),
        observability_service=SimpleNamespace(record_mode_guard_block=lambda **_kwargs: None),
    )


@pytest.fixture(autouse=True)
def _constitution_blocks_unless_bypassed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.order_gatekeeper.evaluate_constitution_for_intent",
        lambda **_kwargs: (False, "constitution_block"),
    )
    monkeypatch.setattr("lumina_core.order_gatekeeper.is_stale_contract_symbol", lambda *_a, **_k: False)
    monkeypatch.setattr(
        "lumina_core.order_gatekeeper.broker_metadata_contract_allowed",
        lambda *_a, **_k: (True, "ok"),
    )


@pytest.mark.unit
def test_sim_learning_keeps_risk_enforced_false() -> None:
    sim = resolve_mode_capabilities("sim")
    paper = resolve_mode_capabilities("paper")
    sim_real_guard = resolve_mode_capabilities("sim_real_guard")
    real = resolve_mode_capabilities("real")

    assert sim.risk_enforced is False
    assert sim.is_learning_mode is True
    assert paper.risk_enforced is False
    assert sim_real_guard.risk_enforced is True
    assert real.risk_enforced is True


@pytest.mark.unit
@pytest.mark.parametrize("trade_mode", ["real", "sim_real_guard"])
def test_env_bypass_fails_in_sim_real_guard_and_real_via_gate(
    trade_mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LUMINA_ADMISSION_BYPASS_STEPS", ADMISSION_STEP_CONSTITUTION)
    engine = _make_engine(trade_mode=trade_mode)

    allowed, reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        order_side="BUY",
    )

    assert allowed is False
    assert "experimental_bypass_forbidden" in reason
    assert "constitution_block" not in reason
    last = engine.admission_chain_trace[-1]
    assert last["step_id"] == ADMISSION_STEP_CONSTITUTION
    assert last["ok"] is False
    assert last["bypassed"] is False


@pytest.mark.unit
@pytest.mark.parametrize("trade_mode", ["sim", "paper"])
def test_env_bypass_remains_logged_lab_only_when_risk_not_enforced(
    trade_mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    warnings: list[str] = []
    monkeypatch.setenv("LUMINA_ADMISSION_BYPASS_STEPS", ADMISSION_STEP_CONSTITUTION)
    engine = _make_engine(trade_mode=trade_mode)
    engine.app = SimpleNamespace(logger=SimpleNamespace(warning=lambda message: warnings.append(str(message))))

    allowed, _reason = enforce_pre_trade_gate(
        engine,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        order_side="BUY",
    )

    assert allowed is True
    constitution_step = next(
        item for item in engine.admission_chain_trace if item["step_id"] == ADMISSION_STEP_CONSTITUTION
    )
    assert constitution_step["bypassed"] is True
    assert constitution_step["ok"] is True
    assert any("ADMISSION_EXPERIMENTAL_BYPASS" in item for item in warnings)
