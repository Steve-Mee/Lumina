"""Fail-closed constitution tests for code evolution v1."""

from __future__ import annotations

from lumina_core.code_evolution.constitution import CodeEvolutionConstitution
from lumina_core.code_evolution.proposal import CodeMutationOperator, CodeMutationProposal


def _param_proposal(**kwargs):
    base = dict(
        proposal_id="p1",
        operator=CodeMutationOperator.PARAMETER_TWEAK,
        target="sandbox.params",
        description="tweak",
        payload={"key": "ema_fast_window", "old_value": 8.0, "new_value": 9.0},
        rationale="test",
        estimated_loc=1,
        before_snapshot={"ema_fast_window": 8.0},
        after_snapshot={"ema_fast_window": 9.0},
    )
    base.update(kwargs)
    return CodeMutationProposal(**base)


def test_parameter_tweak_within_bounds_passes():
    c = CodeEvolutionConstitution()
    res = c.check_pre_mutation(_param_proposal())
    assert res.passed
    assert res.violation_names == []


def test_parameter_out_of_bounds_fails():
    c = CodeEvolutionConstitution()
    res = c.check_pre_mutation(
        _param_proposal(payload={"key": "ema_fast_window", "old_value": 8.0, "new_value": 99.0})
    )
    assert not res.passed
    assert "parameter_out_of_bounds" in res.violation_names


def test_forbidden_risk_parameter_fails():
    c = CodeEvolutionConstitution()
    res = c.check_pre_mutation(
        _param_proposal(
            payload={"key": "max_risk_percent", "old_value": 1.0, "new_value": 2.0},
            before_snapshot={"max_risk_percent": 1.0},
        )
    )
    assert not res.passed
    assert any("no_risk_path_touch" in n or "forbidden" in n for n in res.violation_names)


def test_forbidden_target_fails():
    c = CodeEvolutionConstitution()
    res = c.check_pre_mutation(_param_proposal(target="lumina_core/risk/final_arbitration.py"))
    assert not res.passed
    assert "whitelisted_target" in res.violation_names or "no_risk_path_touch" in res.violation_names


def test_pre_promotion_always_blocks_live_apply():
    c = CodeEvolutionConstitution()
    res = c.check_pre_promotion(_param_proposal())
    assert not res.passed
    assert "v1_evaluate_only" in res.violation_names
