from __future__ import annotations

import pytest

from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_policy import RiskPolicy


def _base_policy() -> RiskPolicy:
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


def _base_state() -> dict[str, float | str | dict[str, float]]:
    return {
        "runtime_mode": "real",
        "daily_pnl": 120.0,
        "account_equity": 25_000.0,
        "drawdown_pct": 4.0,
        "drawdown_kill_percent": 20.0,
        "used_margin": 1_000.0,
        "free_margin": 8_000.0,
        "open_risk_by_symbol": {"MES": 20.0},
        "total_open_risk": 40.0,
        "var_95_usd": 120.0,
        "var_99_usd": 180.0,
        "es_95_usd": 180.0,
        "es_99_usd": 220.0,
        "live_position_qty": 0,
    }


@pytest.mark.unit
def test_final_arbitration_rejects_constitution_violation() -> None:
    arbitration = FinalArbitration(_base_policy())
    intent = {
        "symbol": "MES",
        "side": "BUY",
        "quantity": 1,
        "proposed_risk": 10.0,
        "disable_risk_controller": True,
        "metadata": {},
    }
    result = arbitration.check_order_intent(intent, _base_state())
    assert result.status == "REJECTED"
    assert result.reason.startswith("constitution_violation:")


@pytest.mark.unit
def test_final_arbitration_rejects_risk_limit_overshoot() -> None:
    arbitration = FinalArbitration(_base_policy())
    intent = {
        "symbol": "MES",
        "side": "BUY",
        "quantity": 1,
        "proposed_risk": 150.0,
        "metadata": {},
    }
    result = arbitration.check_order_intent(intent, _base_state())
    assert result.status == "REJECTED"
    assert result.reason == "risk_limit_per_instrument_exceeded"


@pytest.mark.unit
def test_final_arbitration_rejects_low_margin_confidence() -> None:
    arbitration = FinalArbitration(_base_policy())
    intent = {
        "symbol": "MES",
        "side": "BUY",
        "quantity": 1,
        "proposed_risk": 20.0,
        "metadata": {},
    }
    state = _base_state()
    state["used_margin"] = 9_000.0
    state["free_margin"] = 1_000.0
    result = arbitration.check_order_intent(intent, state)
    assert result.status == "REJECTED"
    assert result.reason == "margin_confidence_below_policy"


@pytest.mark.unit
def test_final_arbitration_approves_valid_order() -> None:
    arbitration = FinalArbitration(_base_policy())
    intent = {
        "symbol": "MES",
        "side": "BUY",
        "quantity": 1,
        "proposed_risk": 25.0,
        "reference_price": 5100.0,
        "stop_loss": 5075.0,
        "metadata": {"reason": "entry_signal"},
    }
    result = arbitration.check_order_intent(intent, _base_state())
    assert result.status == "APPROVED"
    assert result.reason == "approved"
