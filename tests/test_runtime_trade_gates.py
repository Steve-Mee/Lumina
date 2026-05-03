from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.runtime_trade_gates import apply_hard_risk_controller_to_signal


@pytest.mark.unit
def test_runtime_trade_gates_blocks_strict_mode_without_final_arbitration() -> None:
    # gegeven
    warnings: list[str] = []
    logger = SimpleNamespace(warning=lambda message, *_args: warnings.append(str(message)))
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real"),
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
    assert reason == "final_arbitration_unavailable"
    assert warnings and "FinalArbitration unavailable in strict mode" in warnings[0]
