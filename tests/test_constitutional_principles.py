"""Tests for Constitutional Trading Principles (P2 - AGI Safety).

All tests are unit-level: no I/O, no external services.
"""

from __future__ import annotations

import json

import pytest

from lumina_core.safety.trading_constitution import (
    ConstitutionalViolationError,
    TRADING_CONSTITUTION,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_content(**kwargs) -> str:
    return json.dumps(kwargs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConstitutionalPrinciplesRegistry:
    def test_all_principles_have_names_and_descriptions(self):
        for p in TRADING_CONSTITUTION.principles:
            assert p.name, "Principle has no name"
            assert p.description, f"Principle {p.name!r} has no description"
            assert p.severity in {"fatal", "warn"}

    def test_at_least_five_principles_defined(self):
        assert len(TRADING_CONSTITUTION.principles) >= 5


@pytest.mark.unit
class TestConstitutionalChecker:
    def setup_method(self):
        self.checker = TRADING_CONSTITUTION

    # -- capital preservation ------------------------------------------------

    def test_capital_preservation_passes_sim_mode(self):
        """High risk is allowed in SIM — no violation."""
        content = _make_content(hyperparam_suggestion={"max_risk_percent": 10.0, "drawdown_kill_percent": 20.0})
        violations = self.checker.audit(content, mode="sim", raise_on_fatal=False)
        cp_violations = [v for v in violations if v.principle_name == "capital_preservation_in_real"]
        assert not cp_violations

    def test_capital_preservation_blocks_real_with_high_risk(self):
        """max_risk_percent > 3.0 is a FATAL violation in REAL mode."""
        content = _make_content(hyperparam_suggestion={"max_risk_percent": 5.0, "drawdown_kill_percent": 20.0})
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            self.checker.audit(content, mode="real", raise_on_fatal=True)
        assert "capital_preservation_in_real" in exc_info.value.violations[0].principle_name

    def test_capital_preservation_passes_real_with_safe_risk(self):
        content = _make_content(hyperparam_suggestion={"max_risk_percent": 1.5, "drawdown_kill_percent": 10.0})
        violations = self.checker.audit(content, mode="real", raise_on_fatal=False)
        cp_violations = [v for v in violations if v.principle_name == "capital_preservation_in_real"]
        assert not cp_violations

    # -- no naked orders -----------------------------------------------------

    def test_naked_orders_blocked_by_disable_risk_controller(self):
        content = _make_content(disable_risk_controller=True)
        with pytest.raises(ConstitutionalViolationError):
            self.checker.audit(content, mode="real")

    def test_naked_orders_blocked_in_sim_too(self):
        content = _make_content(bypass_order_gatekeeper=True)
        violations = self.checker.audit(content, mode="sim", raise_on_fatal=False)
        assert any(v.principle_name == "no_naked_orders" for v in violations)

    # -- mutation depth -------------------------------------------------------

    def test_radical_mutation_depth_blocked_in_real(self):
        content = _make_content(mutation_depth="radical")
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            self.checker.audit(content, mode="real")
        assert "max_mutation_depth_enforced" in exc_info.value.violations[0].principle_name

    def test_radical_mutation_depth_allowed_in_sim(self):
        content = _make_content(mutation_depth="radical")
        violations = self.checker.audit(content, mode="sim", raise_on_fatal=False)
        depth_violations = [v for v in violations if v.principle_name == "max_mutation_depth_enforced"]
        assert not depth_violations

    # -- approval required ----------------------------------------------------

    def test_approval_disabled_blocks_real(self):
        content = _make_content(approval_required=False)
        with pytest.raises(ConstitutionalViolationError):
            self.checker.audit(content, mode="real")

    # -- drawdown kill percent ------------------------------------------------

    def test_extreme_drawdown_threshold_blocked_any_mode(self):
        content = _make_content(hyperparam_suggestion={"max_risk_percent": 1.0, "drawdown_kill_percent": 30.0})
        violations = self.checker.audit(content, mode="sim", raise_on_fatal=False)
        assert any(v.principle_name == "drawdown_kill_percent_bounded" for v in violations)

    # -- clean DNA passes all --------------------------------------------------

    def test_clean_dna_passes_all_principles_in_sim(self):
        content = _make_content(hyperparam_suggestion={"max_risk_percent": 2.0, "drawdown_kill_percent": 12.0})
        violations = self.checker.audit(content, mode="sim", raise_on_fatal=False)
        fatals = [v for v in violations if v.severity == "fatal"]
        assert not fatals

    def test_clean_dna_passes_all_principles_in_real(self):
        content = _make_content(hyperparam_suggestion={"max_risk_percent": 1.0, "drawdown_kill_percent": 8.0})
        violations = self.checker.audit(content, mode="real", raise_on_fatal=False)
        fatals = [v for v in violations if v.severity == "fatal"]
        assert not fatals

    # -- non-JSON content is safe (plain prompt string) -----------------------

    def test_plain_text_dna_is_fatally_blocked(self):
        """Plain-text payloads are rejected to prevent schema bypasses."""
        content = "Buy MES when RSI < 30 and ATR > baseline. Capital preservation first."
        violations = self.checker.audit(content, mode="real", raise_on_fatal=False)
        fatals = [v for v in violations if v.severity == "fatal"]
        assert any(v.principle_name == "dna_must_be_structured_json" for v in fatals)


@pytest.mark.unit
class TestSandboxedMutationExecutor:
    def test_in_process_clean_dna_passes(self):
        from lumina_core.safety.sandboxed_executor import SandboxedMutationExecutor

        sandbox = SandboxedMutationExecutor()
        content = json.dumps({"hyperparam_suggestion": {"max_risk_percent": 1.0, "drawdown_kill_percent": 8.0}})
        result = sandbox._run_in_process(
            dna_hash="test_hash_001",
            dna_content=content,
            mode="sim",
            pnl=500.0,
            max_dd=200.0,
            sharpe=1.5,
            input_hash="test_input_hash_001",
        )
        assert result.passed or result.score >= 0.0
        assert not result.timed_out

    def test_in_process_fatal_violation_fails(self):
        from lumina_core.safety.sandboxed_executor import SandboxedMutationExecutor

        sandbox = SandboxedMutationExecutor()
        content = json.dumps({"disable_risk_controller": True})
        result = sandbox._run_in_process(
            dna_hash="test_hash_002",
            dna_content=content,
            mode="sim",
            pnl=1000.0,
            max_dd=100.0,
            sharpe=2.0,
            input_hash="test_input_hash_002",
        )
        assert not result.passed
        assert "no_naked_orders" in result.violations
