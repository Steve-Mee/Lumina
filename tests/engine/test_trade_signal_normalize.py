from __future__ import annotations

import pytest

from lumina_core.engine.trade_signal_normalize import canonicalize_trade_signal


@pytest.mark.parametrize(
    ("raw", "expect"),
    [
        ("BUY", "BUY"),
        ("sell", "SELL"),
        ("  Hold ", "HOLD"),
        ("", "HOLD"),
        (None, "HOLD"),
        ("NONE", "HOLD"),
        ("None", "HOLD"),
        ("long", "BUY"),
        ("SHORT", "SELL"),
        ("FLAT", "HOLD"),
        ("junk_xyz", "HOLD"),
    ],
)
def test_canonicalize_trade_signal(raw: object, expect: str) -> None:
    assert canonicalize_trade_signal(raw) == expect


def test_execution_decision_schema_coerces_python_none_string() -> None:
    """Regression: stray None coerced JSON must not yield invalid_signal at gateway."""
    from lumina_core.engine.agent_contracts import ExecutionDecisionInputSchema

    m = ExecutionDecisionInputSchema.model_validate(
        {
            "signal": "None",
            "confluence_score": 0.0,
            "min_confluence": 0.75,
            "hold_until_ts": 0.0,
            "timestamp": "2026-05-04T00:00:00+00:00",
        }
    )
    assert m.signal == "HOLD"
