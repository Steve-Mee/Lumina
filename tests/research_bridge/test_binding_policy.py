"""D9/D10/D11 proposal-only mapping. Never places."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from lumina_core.research_bridge.binding_policy import (
    DISABLE_FLATTEN_FRACTION,
    INDEPENDENCE_CORR_MAX,
    SLA_ESCALATE_AFTER_SECONDS,
    SLA_RETRY_LIMIT,
    SUSPEND_REDUCE_FRACTION,
    BindingPolicyRefused,
    independent,
    reduce_fraction_for_stage,
    reduce_qty,
    sla_decision,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.safety_gate
def test_d9_size_map() -> None:
    assert SUSPEND_REDUCE_FRACTION == 0.5
    assert DISABLE_FLATTEN_FRACTION == 1.0
    assert reduce_fraction_for_stage("deweighted") == 0.5
    assert reduce_fraction_for_stage("suspended") == 0.5
    assert reduce_fraction_for_stage("retired") == 1.0
    assert reduce_fraction_for_stage("critical") == 1.0
    assert reduce_fraction_for_stage("disabled") == 1.0
    assert reduce_qty("suspended", 2) == 1
    assert reduce_qty("retired", 2) == 2
    with pytest.raises(BindingPolicyRefused):
        reduce_fraction_for_stage("increase")
    with pytest.raises(BindingPolicyRefused):
        reduce_qty("suspended", 1)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_d10_sla() -> None:
    assert SLA_RETRY_LIMIT == 1
    assert SLA_ESCALATE_AFTER_SECONDS == 600
    assert sla_decision(1, 10.0) == "retry"
    assert sla_decision(2, 10.0) == "escalate"
    assert sla_decision(1, 600.0) == "retry"
    assert sla_decision(1, 601.0) == "escalate"
    assert sla_decision(3, 1.0) == "escalate"
    with pytest.raises(BindingPolicyRefused):
        sla_decision(0, 1.0)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_d11_independence_both_clauses() -> None:
    assert INDEPENDENCE_CORR_MAX == 0.5
    ok, reason = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=0.3,
    )
    assert ok is True
    assert reason == "independent"
    same_family, why = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="trend",
        config_id="c1",
        other_config_id="c2",
        correlation=0.2,
    )
    assert same_family is False
    assert why == "survivors_same_family"
    high_corr, why2 = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=0.7,
    )
    assert high_corr is False
    assert why2 == "survivors_corr_not_independent"
    at_threshold, why3 = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=0.5,
    )
    assert at_threshold is False
    missing, why4 = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=None,
    )
    assert missing is False
    assert why4 == "survivors_corr_unavailable"
    clone, why5 = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h2",
        other_family="meanrev",
        config_id="same",
        other_config_id="same",
        correlation=0.1,
    )
    assert clone is False
    assert why5 == "survivors_same_config"
    same_h, why6 = independent(
        hypothesis_id="h1",
        family="trend",
        other_hypothesis_id="h1",
        other_family="meanrev",
        config_id="c1",
        other_config_id="c2",
        correlation=0.1,
    )
    assert same_h is False
    assert why6 == "survivors_same_hypothesis"
    assert reduce_qty("disabled", 3) == 3
    assert reduce_qty("hard_limit", 4) == 4
    assert reduce_fraction_for_stage("prolonged_disconnect") == 1.0


@pytest.mark.unit
def test_binding_policy_source_has_no_broker_or_place() -> None:
    path = ROOT / "lumina_core" / "research_bridge" / "binding_policy.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("lumina_core.broker")
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("lumina_core.broker")
    assert "place_order" not in source
    assert "submit_order" not in source
