from __future__ import annotations

import pytest

from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_policy import RiskPolicy
from lumina_core.risk.schemas import ArbitrationState, OrderIntent, OrderIntentMetadata


def _policy(mode: str) -> RiskPolicy:
    return RiskPolicy(
        runtime_mode=mode,
        daily_loss_cap=-1_000.0,
        max_open_risk_per_instrument=1_000.0,
        max_total_open_risk=4_000.0,
        var_95_limit_usd=2_500.0,
        var_99_limit_usd=3_000.0,
        es_95_limit_usd=2_800.0,
        es_99_limit_usd=3_200.0,
        margin_min_confidence=0.5,
    )


def _state(mode: str, *, snapshot_ok: bool, snapshot_reason: str, live_position_qty: int = 0) -> ArbitrationState:
    return ArbitrationState(
        runtime_mode=mode,
        equity_snapshot_ok=snapshot_ok,
        equity_snapshot_reason=snapshot_reason,
        daily_pnl=500.0,
        account_equity=0.0 if not snapshot_ok else 25_000.0,
        free_margin=0.0 if not snapshot_ok else 12_500.0,
        used_margin=0.0 if not snapshot_ok else 2_500.0,
        margin_confidence=0.9,
        drawdown_pct=2.0,
        drawdown_kill_percent=25.0,
        total_open_risk=100.0,
        live_position_qty=live_position_qty,
    )


def _risk_increasing_intent() -> OrderIntent:
    return OrderIntent(
        instrument="MES",
        side="BUY",
        quantity=1,
        proposed_risk=25.0,
        reference_price=5100.0,
        stop=5075.0,
        confidence=0.8,
        source_agent="unit-test",
        metadata=OrderIntentMetadata(reason="entry_signal"),
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("mode", "expected_reason"),
    [
        ("real", "real_equity_snapshot_required"),
        ("paper", "paper_equity_snapshot_required"),
        ("sim_real_guard", "sim_real_guard_equity_snapshot_required"),
    ],
)
def test_risk_increase_rejects_when_snapshot_missing_even_with_skip_request(mode: str, expected_reason: str) -> None:
    # gegeven
    arbitration = FinalArbitration(_policy(mode))

    # wanneer
    result = arbitration.check_order_intent(
        _risk_increasing_intent(),
        _state(mode, snapshot_ok=False, snapshot_reason=expected_reason),
        skip_internal_steps=frozenset({"constitution", "risk_policy", "real_equity_snapshot"}),
    )

    # dan
    assert result.status == "REJECTED"
    assert result.reason == expected_reason
    check_reasons = {check.name: check.reason for check in result.checks}
    assert check_reasons["real_equity_snapshot"] == expected_reason


@pytest.mark.unit
def test_real_risk_reducing_exit_is_allowed_without_snapshot() -> None:
    # gegeven
    arbitration = FinalArbitration(_policy("real"))
    intent = OrderIntent(
        instrument="MES",
        side="SELL",
        quantity=1,
        proposed_risk=25.0,
        confidence=0.7,
        source_agent="unit-test",
        metadata=OrderIntentMetadata(reason="risk_reducing_exit"),
    )
    state = _state("real", snapshot_ok=False, snapshot_reason="real_equity_snapshot_required", live_position_qty=1)

    # wanneer
    result = arbitration.check_order_intent(
        intent,
        state,
        skip_internal_steps=frozenset({"constitution", "risk_policy", "real_equity_snapshot"}),
    )

    # dan
    assert result.status == "APPROVED"
    assert result.reason == "approved_eod_force_close_exit"
