"""Controller / operator catalog tests."""

from __future__ import annotations

from lumina_core.code_evolution.operators import CodeEvolutionController, validate_parameter_tweak
from lumina_core.code_evolution.proposal import CodeMutationOperator


def test_disabled_controller_proposes_nothing():
    ctrl = CodeEvolutionController(enabled=False)
    assert ctrl.propose(seed="x") == []


def test_enabled_controller_proposes_param_tweak():
    ctrl = CodeEvolutionController(enabled=True, max_proposals_per_cycle=1)
    props = ctrl.propose(seed="abc")
    assert len(props) == 1
    assert props[0].operator == CodeMutationOperator.PARAMETER_TWEAK
    assert props[0].target == "sandbox.params"


def test_validate_parameter_tweak_bounds():
    assert validate_parameter_tweak("ema_fast_window", 8.0, 9.0) == []
    assert "parameter_out_of_bounds" in validate_parameter_tweak("ema_fast_window", 8.0, 100.0)
    assert "parameter_not_whitelisted" in validate_parameter_tweak("unknown_key", 1.0, 2.0)
    assert "forbidden_parameter_key" in validate_parameter_tweak("max_risk_percent", 1.0, 1.1)
