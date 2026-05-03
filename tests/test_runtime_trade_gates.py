from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.runtime_trade_gates import apply_hard_risk_controller_to_signal
from lumina_core.agent_orchestration.schemas import TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC


@pytest.mark.unit
def test_runtime_trade_gates_blocks_strict_mode_without_final_arbitration() -> None:
    # gegeven
    warnings: list[str] = []
    logger = SimpleNamespace(warning=lambda message, *_args: warnings.append(str(message)))
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real"),
        risk_controller=SimpleNamespace(
            _active_limits=SimpleNamespace(enforce_session_guard=False),
            apply_regime_override=lambda *_a, **_k: None,
            check_can_trade=lambda *_a, **_k: (True, "OK"),
            check_var_es_pre_trade=lambda *_a, **_k: (True, "VAR_ES OK", {}),
            check_monte_carlo_drawdown_pre_trade=lambda *_a, **_k: (True, "MC drawdown OK", {}),
            record_regime_snapshot=lambda *_a, **_k: None,
        ),
        reasoning_service=SimpleNamespace(
            refresh_regime_snapshot=lambda: {"label": "NEUTRAL", "risk_state": "NORMAL", "adaptive_policy": {}}
        ),
        blackboard=SimpleNamespace(
            latest=lambda topic: (
                SimpleNamespace(
                    payload={"agent_id": "rl", "confidence": 0.9, "reason": "test"},
                    producer="test",
                    confidence=0.9,
                    timestamp="2026-05-03T00:00:00+00:00",
                    correlation_id="corr",
                    sequence=1,
                    event_hash="hash",
                    prev_hash="prev",
                )
                if topic.startswith("agent.")
                else None
            )
        ),
        event_bus=SimpleNamespace(
            latest=lambda topic: (
                SimpleNamespace(
                    payload={"signal": "BUY", "chosen_strategy": "rl", "confidence": 0.9},
                    producer="test",
                    timestamp="2026-05-03T00:00:00+00:00",
                    metadata={"sequence": 1, "correlation_id": "corr"},
                    to_dict=lambda: {},
                )
                if topic == TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
                else None
            )
        ),
        audit_log_service=SimpleNamespace(log_decision=lambda *_a, **_k: True),
        get_current_dream_snapshot=lambda: {"confidence": 0.9, "expected_value": 1.0},
        equity_snapshot_provider=SimpleNamespace(
            get_snapshot=lambda: SimpleNamespace(
                ok=True,
                is_fresh=True,
                source="unit-test",
                reason_code="ok",
                equity_usd=50_000.0,
                available_margin_usd=45_000.0,
                used_margin_usd=5_000.0,
            )
        ),
        account_equity=50_000.0,
        available_margin=45_000.0,
        positions_margin_used=5_000.0,
        live_position_qty=0,
        final_arbitration=None,
        risk_policy=None,
    )

    # wanneer
    signal, ok, reason = apply_hard_risk_controller_to_signal(
        signal="BUY",
        price=5000.0,
        dream_snapshot={"stop": 4990.0, "confidence": 0.9},
        instrument="MES",
        risk_controller=None,
        logger=logger,
        mode="real",
        engine=engine,
    )

    # dan
    assert signal == "HOLD"
    assert ok is False
    assert "final_arbitration_unavailable" in reason
    assert warnings and "AdmissionChain blocked runtime signal" in warnings[0]
