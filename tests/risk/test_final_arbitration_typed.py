from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.risk.final_arbitration import FinalArbitration, build_order_intent_from_order
from lumina_core.risk.risk_policy import RiskPolicy
from lumina_core.risk.schemas import ArbitrationCheckStep, ArbitrationState, OrderIntent, OrderIntentMetadata


def _policy() -> RiskPolicy:
    return RiskPolicy(
        daily_loss_cap=-500.0,
        max_open_risk_per_instrument=100.0,
        max_total_open_risk=300.0,
        max_exposure_per_regime=250.0,
        kelly_fraction=0.2,
        var_95_limit_usd=400.0,
        var_99_limit_usd=600.0,
        es_95_limit_usd=500.0,
        es_99_limit_usd=700.0,
        margin_min_confidence=0.6,
        runtime_mode="real",
    )


def _state() -> ArbitrationState:
    return ArbitrationState(
        runtime_mode="real",
        equity_snapshot_ok=True,
        equity_snapshot_reason="ok",
        daily_pnl=100.0,
        account_equity=25_000.0,
        drawdown_pct=2.0,
        drawdown_kill_percent=20.0,
        used_margin=1_000.0,
        free_margin=8_000.0,
        open_risk_by_symbol={"MES": 20.0},
        total_open_risk=40.0,
        var_95_usd=100.0,
        var_99_usd=150.0,
        es_95_usd=120.0,
        es_99_usd=180.0,
        live_position_qty=0,
    )


@pytest.mark.unit
def test_build_order_intent_from_order_returns_order_intent_model() -> None:
    # gegeven
    order = SimpleNamespace(
        symbol="MES",
        side="BUY",
        quantity=1,
        order_type="MARKET",
        stop_loss=5090.0,
        take_profit=5120.0,
        metadata={
            "reference_price": 5100.0,
            "proposed_risk": 10.0,
            "source_agent": "signal-agent",
            "confidence": 0.88,
            "reason": "entry_signal",
        },
    )

    # wanneer
    intent = build_order_intent_from_order(order, dream_snapshot={"regime": "TREND"})

    # dan
    assert isinstance(intent, OrderIntent)
    assert intent.instrument == "MES"
    assert intent.confidence == pytest.approx(0.88)
    assert intent.source_agent == "signal-agent"


@pytest.mark.unit
def test_typed_arbitration_result_sets_violated_principle_on_constitution_reject() -> None:
    # gegeven
    arbitration = FinalArbitration(_policy())
    intent = OrderIntent(
        instrument="MES",
        side="BUY",
        quantity=1,
        proposed_risk=10.0,
        confidence=0.9,
        source_agent="signal-agent",
        disable_risk_controller=True,
        metadata=OrderIntentMetadata(reason="entry_signal"),
    )

    # wanneer
    result = arbitration.check_order_intent(intent, _state())

    # dan
    assert result.status == "REJECTED"
    assert result.reason.startswith("constitution_violation:")
    assert result.violated_principle
    assert result.checks
    assert all(isinstance(step, ArbitrationCheckStep) for step in result.checks)
