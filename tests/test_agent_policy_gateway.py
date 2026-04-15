from __future__ import annotations

from lumina_core.engine.agent_contracts import apply_agent_policy_gateway


def _lineage() -> dict[str, object]:
    return {
        "model_identifier": "unit-test-model",
        "prompt_version": "unit-v1",
        "prompt_hash": "abc123",
        "policy_version": "agent-policy-gateway-v1",
        "provider_route": ["unit-provider"],
        "calibration_factor": 1.0,
    }


def test_policy_gateway_accepts_valid_buy() -> None:
    result = apply_agent_policy_gateway(
        signal="BUY",
        confluence_score=0.82,
        min_confluence=0.75,
        hold_until_ts=0.0,
        mode="sim",
        session_allowed=True,
        risk_allowed=True,
        lineage=_lineage(),
    )

    assert result["approved"] is True
    assert result["signal"] == "BUY"
    assert result["reason"] == "accepted"


def test_policy_gateway_blocks_session_bypass() -> None:
    result = apply_agent_policy_gateway(
        signal="SELL",
        confluence_score=0.9,
        min_confluence=0.7,
        hold_until_ts=0.0,
        mode="real",
        session_allowed=False,
        risk_allowed=True,
        lineage=_lineage(),
    )

    assert result["approved"] is False
    assert result["signal"] == "HOLD"
    assert result["reason"] == "session_blocked"


def test_policy_gateway_blocks_risk_rejection() -> None:
    result = apply_agent_policy_gateway(
        signal="BUY",
        confluence_score=0.95,
        min_confluence=0.6,
        hold_until_ts=0.0,
        mode="real",
        session_allowed=True,
        risk_allowed=False,
        lineage=_lineage(),
    )

    assert result["approved"] is False
    assert result["signal"] == "HOLD"
    assert result["reason"] == "risk_blocked"


def test_policy_gateway_accepts_sim_real_guard_mode() -> None:
    result = apply_agent_policy_gateway(
        signal="BUY",
        confluence_score=0.9,
        min_confluence=0.75,
        hold_until_ts=0.0,
        mode="sim_real_guard",
        session_allowed=True,
        risk_allowed=True,
        lineage=_lineage(),
    )

    assert result["approved"] is True
    assert result["signal"] == "BUY"
    assert result["reason"] == "accepted"
