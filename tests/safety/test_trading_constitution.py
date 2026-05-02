"""Tests for TradingConstitution — all principles, audit logic, and edge cases.

Every test here is @unit (no I/O, no subprocess, no external services).
"""

from __future__ import annotations

import json

import pytest

from lumina_core.safety.trading_constitution import (
    TRADING_CONSTITUTION,
    ConstitutionalViolation,
    ConstitutionalViolationError,
    _parse_dna_content,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal non-empty JSON object accepted by _parse_dna_content (empty `{}` is invalid).
_MINIMAL_VALID_DNA = json.dumps({"stub": True})


def _dna(**kwargs: object) -> str:
    return json.dumps(kwargs)


def _hs(**kwargs: object) -> str:
    """Build a DNA with hyperparam_suggestion dict."""
    return json.dumps({"hyperparam_suggestion": dict(kwargs)})


def _audit(dna: str, mode: str = "real") -> list[ConstitutionalViolation]:
    return TRADING_CONSTITUTION.audit(dna, mode=mode, raise_on_fatal=False)


def _fatal_names(dna: str, mode: str = "real") -> list[str]:
    return [v.principle_name for v in _audit(dna, mode) if v.severity == "fatal"]


def _warn_names(dna: str, mode: str = "real") -> list[str]:
    return [v.principle_name for v in _audit(dna, mode) if v.severity == "warn"]


# ---------------------------------------------------------------------------
# Meta: constitution structure
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConstitutionStructure:

    def test_has_16_principles(self) -> None:
        assert len(TRADING_CONSTITUTION.principles) == 16

    def test_at_least_12_fatal_principles(self) -> None:
        assert TRADING_CONSTITUTION.fatal_count >= 12

    def test_at_least_2_warn_principles(self) -> None:
        assert TRADING_CONSTITUTION.warn_count >= 2

    def test_all_principles_have_rationale(self) -> None:
        for p in TRADING_CONSTITUTION.principles:
            assert p.rationale, f"Principle {p.name!r} has no rationale"

    def test_all_principles_have_unique_names(self) -> None:
        names = [p.name for p in TRADING_CONSTITUTION.principles]
        assert len(names) == len(set(names)), "Duplicate principle names detected"

    def test_all_principles_have_valid_severity(self) -> None:
        for p in TRADING_CONSTITUTION.principles:
            assert p.severity in {"fatal", "warn"}, \
                f"Principle {p.name!r} has invalid severity {p.severity!r}"

    def test_constitution_is_immutable(self) -> None:
        """Principles tuple must be truly immutable."""
        with pytest.raises((TypeError, AttributeError)):
            TRADING_CONSTITUTION.principles[0] = TRADING_CONSTITUTION.principles[1]  # type: ignore[index]

    def test_clean_dna_passes_all_principles(self) -> None:
        violations = _audit(_MINIMAL_VALID_DNA, mode="sim")
        assert not any(v.severity == "fatal" for v in violations)

    def test_plain_text_dna_is_fatal_fail_closed(self) -> None:
        """Plain-text DNA is rejected (structured JSON required)."""
        violations = _audit("Be conservative, use small position sizes.", mode="real")
        assert any(
            v.principle_name == "dna_must_be_structured_json" and v.severity == "fatal" for v in violations
        )


# ---------------------------------------------------------------------------
# Principle 1 — capital_preservation_in_real
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCapitalPreservation:

    def test_max_risk_3_percent_ok(self) -> None:
        dna = _hs(max_risk_percent=3.0)
        assert "capital_preservation_in_real" not in _fatal_names(dna)

    def test_max_risk_2_percent_ok(self) -> None:
        assert "capital_preservation_in_real" not in _fatal_names(_hs(max_risk_percent=2.0))

    def test_max_risk_3_1_percent_fatal_real(self) -> None:
        assert "capital_preservation_in_real" in _fatal_names(_hs(max_risk_percent=3.1))

    def test_max_risk_10_percent_fatal_real(self) -> None:
        assert "capital_preservation_in_real" in _fatal_names(_hs(max_risk_percent=10.0))

    def test_max_risk_ignored_in_sim(self) -> None:
        assert "capital_preservation_in_real" not in _fatal_names(_hs(max_risk_percent=99.0), mode="sim")

    def test_missing_max_risk_passes(self) -> None:
        assert "capital_preservation_in_real" not in _fatal_names(_MINIMAL_VALID_DNA)


# ---------------------------------------------------------------------------
# Principle 2 — no_naked_orders
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoNakedOrders:

    @pytest.mark.parametrize("key", [
        "disable_risk_controller",
        "bypass_order_gatekeeper",
        "skip_var_check",
        "no_capital_floor",
        "disable_hard_risk",
        "disable_kill_switch",
        "disable_position_limits",
        "no_gatekeeper",
    ])
    def test_bypass_key_triggers_fatal(self, key: str) -> None:
        dna = json.dumps({key: True})
        assert "no_naked_orders" in _fatal_names(dna, mode="sim")

    def test_bypass_key_false_passes(self) -> None:
        dna = _dna(disable_risk_controller=False)
        assert "no_naked_orders" not in _fatal_names(dna)

    def test_no_bypass_keys_passes(self) -> None:
        assert "no_naked_orders" not in _fatal_names(_MINIMAL_VALID_DNA)


# ---------------------------------------------------------------------------
# Principle 3 — max_mutation_depth_enforced
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMutationDepth:

    @pytest.mark.parametrize("depth", ["radical", "aggressive", "extreme", "unconstrained"])
    def test_radical_depth_fatal_real(self, depth: str) -> None:
        dna = _dna(mutation_depth=depth)
        assert "max_mutation_depth_enforced" in _fatal_names(dna, mode="real")

    def test_conservative_depth_ok_real(self) -> None:
        dna = _dna(mutation_depth="conservative")
        assert "max_mutation_depth_enforced" not in _fatal_names(dna, mode="real")

    def test_moderate_depth_ok_real(self) -> None:
        dna = _dna(mutation_depth="moderate")
        assert "max_mutation_depth_enforced" not in _fatal_names(dna, mode="real")

    def test_radical_depth_ok_sim(self) -> None:
        dna = _dna(mutation_depth="radical")
        assert "max_mutation_depth_enforced" not in _fatal_names(dna, mode="sim")


# ---------------------------------------------------------------------------
# Principle 4 — approval_required_in_real
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestApprovalRequired:

    def test_approval_required_false_fatal_real(self) -> None:
        assert "approval_required_in_real" in _fatal_names(_dna(approval_required=False))

    def test_skip_human_approval_fatal_real(self) -> None:
        assert "approval_required_in_real" in _fatal_names(_dna(skip_human_approval=True))

    def test_auto_approve_real_fatal(self) -> None:
        assert "approval_required_in_real" in _fatal_names(_dna(auto_approve_real=True))

    def test_approval_required_true_passes(self) -> None:
        assert "approval_required_in_real" not in _fatal_names(_dna(approval_required=True))

    def test_no_approval_key_passes(self) -> None:
        assert "approval_required_in_real" not in _fatal_names(_MINIMAL_VALID_DNA)

    def test_approval_bypass_ignored_in_sim(self) -> None:
        assert "approval_required_in_real" not in _fatal_names(
            _dna(approval_required=False), mode="sim"
        )


# ---------------------------------------------------------------------------
# Principle 5 — no_synthetic_data_in_real_neuro
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoSyntheticDataNeuro:

    def test_require_real_false_fatal_real(self) -> None:
        dna = _dna(neuroevolution={"require_real_simulator_data": False})
        assert "no_synthetic_data_in_real_neuro" in _fatal_names(dna)

    def test_synthetic_only_fatal_real(self) -> None:
        dna = _dna(neuroevolution={"synthetic_only": True})
        assert "no_synthetic_data_in_real_neuro" in _fatal_names(dna)

    def test_real_data_required_passes(self) -> None:
        dna = _dna(neuroevolution={"require_real_simulator_data": True})
        assert "no_synthetic_data_in_real_neuro" not in _fatal_names(dna)

    def test_synthetic_false_ignored_in_sim(self) -> None:
        dna = _dna(neuroevolution={"require_real_simulator_data": False})
        assert "no_synthetic_data_in_real_neuro" not in _fatal_names(dna, mode="sim")


# ---------------------------------------------------------------------------
# Principle 6 — drawdown_kill_percent_bounded
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDrawdownKillBounded:

    def test_25_percent_ok_any_mode(self) -> None:
        for mode in ("real", "sim", "paper"):
            assert "drawdown_kill_percent_bounded" not in _fatal_names(_hs(drawdown_kill_percent=25.0), mode=mode)

    def test_26_percent_fatal_any_mode(self) -> None:
        for mode in ("real", "sim", "paper"):
            assert "drawdown_kill_percent_bounded" in _fatal_names(_hs(drawdown_kill_percent=26.0), mode=mode)

    def test_top_level_key_enforced(self) -> None:
        dna = _dna(drawdown_kill_percent=50.0)
        assert "drawdown_kill_percent_bounded" in _fatal_names(dna, mode="sim")


# ---------------------------------------------------------------------------
# Principle 7 — no_aggressive_evolution_in_real
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoAggressiveEvolution:

    def test_aggressive_evolution_true_fatal_real(self) -> None:
        assert "no_aggressive_evolution_in_real" in _fatal_names(_dna(aggressive_evolution=True))

    def test_evolution_mode_radical_fatal_real(self) -> None:
        assert "no_aggressive_evolution_in_real" in _fatal_names(_dna(evolution_mode="radical"))

    def test_aggressive_evolution_true_ok_sim(self) -> None:
        assert "no_aggressive_evolution_in_real" not in _fatal_names(
            _dna(aggressive_evolution=True), mode="sim"
        )


# ---------------------------------------------------------------------------
# Principle 8 — kelly_fraction_cap
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestKellyFractionCap:

    def test_kelly_025_ok_real(self) -> None:
        assert "kelly_fraction_cap" not in _fatal_names(_dna(kelly_fraction=0.25))

    def test_kelly_026_fatal_real(self) -> None:
        assert "kelly_fraction_cap" in _fatal_names(_dna(kelly_fraction=0.26))

    def test_kelly_1_fatal_real(self) -> None:
        assert "kelly_fraction_cap" in _fatal_names(_dna(kelly_fraction=1.0))

    def test_kelly_in_hs_enforced(self) -> None:
        assert "kelly_fraction_cap" in _fatal_names(_hs(kelly_fraction=0.5))

    def test_kelly_cap_ignored_sim(self) -> None:
        assert "kelly_fraction_cap" not in _fatal_names(_dna(kelly_fraction=1.0), mode="sim")


# ---------------------------------------------------------------------------
# Principle 9 — daily_loss_hard_stop_required
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDailyLossHardStop:

    def test_negative_loss_cap_ok_real(self) -> None:
        dna = _hs(daily_loss_cap=-500.0)
        assert "daily_loss_hard_stop_required" not in _fatal_names(dna)

    def test_zero_loss_cap_fatal_real(self) -> None:
        dna = _hs(daily_loss_cap=0.0)
        assert "daily_loss_hard_stop_required" in _fatal_names(dna)

    def test_positive_loss_cap_fatal_real(self) -> None:
        dna = _hs(daily_loss_cap=100.0)
        assert "daily_loss_hard_stop_required" in _fatal_names(dna)

    def test_disable_daily_loss_cap_fatal(self) -> None:
        dna = _dna(disable_daily_loss_cap=True)
        assert "daily_loss_hard_stop_required" in _fatal_names(dna)

    def test_no_daily_loss_key_passes(self) -> None:
        assert "daily_loss_hard_stop_required" not in _fatal_names(_MINIMAL_VALID_DNA)

    def test_positive_cap_ok_sim(self) -> None:
        dna = _hs(daily_loss_cap=100.0)
        assert "daily_loss_hard_stop_required" not in _fatal_names(dna, mode="sim")


# ---------------------------------------------------------------------------
# Principle 10 — no_leverage_explosion
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoLeverageExplosion:

    def test_leverage_2x_ok_real(self) -> None:
        assert "no_leverage_explosion" not in _fatal_names(_dna(leverage_multiplier=2.0))

    def test_leverage_2_1x_fatal_real(self) -> None:
        assert "no_leverage_explosion" in _fatal_names(_dna(leverage_multiplier=2.1))

    def test_leverage_in_hs_enforced(self) -> None:
        assert "no_leverage_explosion" in _fatal_names(_hs(leverage_multiplier=5.0))

    def test_high_leverage_ok_sim(self) -> None:
        assert "no_leverage_explosion" not in _fatal_names(_dna(leverage_multiplier=10.0), mode="sim")


# ---------------------------------------------------------------------------
# Principle 11 — minimum_backtest_quality_for_real
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestMinimumBacktestQuality:

    def test_sharpe_0_3_ok_real(self) -> None:
        assert "minimum_backtest_quality_for_real" not in _fatal_names(_dna(backtest_sharpe_ratio=0.3))

    def test_sharpe_0_29_fatal_real(self) -> None:
        assert "minimum_backtest_quality_for_real" in _fatal_names(_dna(backtest_sharpe_ratio=0.29))

    def test_negative_sharpe_fatal_real(self) -> None:
        assert "minimum_backtest_quality_for_real" in _fatal_names(_dna(backtest_sharpe_ratio=-1.0))

    def test_missing_sharpe_passes(self) -> None:
        # Absence of backtest data should not block.
        assert "minimum_backtest_quality_for_real" not in _fatal_names(_MINIMAL_VALID_DNA, mode="real")

    def test_bad_sharpe_ok_sim(self) -> None:
        assert "minimum_backtest_quality_for_real" not in _fatal_names(
            _dna(backtest_sharpe_ratio=-5.0), mode="sim"
        )


# ---------------------------------------------------------------------------
# Principle 12 — no_circuit_breaker_disable
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoCircuitBreakerDisable:

    @pytest.mark.parametrize("key", [
        "disable_circuit_breaker",
        "bypass_circuit_breaker",
        "no_circuit_breaker",
        "disable_emergency_halt",
        "skip_halt_check",
    ])
    def test_circuit_breaker_bypass_fatal_any_mode(self, key: str) -> None:
        dna = json.dumps({key: True})
        for mode in ("real", "sim", "paper"):
            assert "no_circuit_breaker_disable" in _fatal_names(dna, mode=mode), \
                f"Expected fatal for {key!r} in {mode!r}"


# ---------------------------------------------------------------------------
# Principle 13 — no_session_guard_bypass
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoSessionGuardBypass:

    @pytest.mark.parametrize("key", [
        "bypass_session_guard",
        "disable_session_guard",
        "trade_outside_session",
        "ignore_session_window",
        "force_trade_closed",
    ])
    def test_session_bypass_fatal_real(self, key: str) -> None:
        dna = json.dumps({key: True})
        assert "no_session_guard_bypass" in _fatal_names(dna, mode="real"), \
            f"Expected fatal for {key!r}"

    def test_session_bypass_ok_sim(self) -> None:
        dna = _dna(bypass_session_guard=True)
        assert "no_session_guard_bypass" not in _fatal_names(dna, mode="sim")


# ---------------------------------------------------------------------------
# Principle 14 — concentration_risk_limit (WARN)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestConcentrationRisk:

    def test_80_percent_ok_real(self) -> None:
        assert "concentration_risk_limit" not in _warn_names(_dna(single_instrument_exposure_pct=80.0))

    def test_81_percent_warn_real(self) -> None:
        assert "concentration_risk_limit" in _warn_names(_dna(single_instrument_exposure_pct=81.0))

    def test_warn_not_fatal(self) -> None:
        dna = _dna(single_instrument_exposure_pct=100.0)
        violations = _audit(dna)
        conc_violations = [v for v in violations if v.principle_name == "concentration_risk_limit"]
        assert conc_violations
        assert all(v.severity == "warn" for v in conc_violations)

    def test_concentration_ignored_sim(self) -> None:
        dna = _dna(single_instrument_exposure_pct=100.0)
        assert "concentration_risk_limit" not in _warn_names(dna, mode="sim")


# ---------------------------------------------------------------------------
# Principle 15 — trade_frequency_guard (WARN)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestTradeFrequencyGuard:

    def test_200_trades_ok(self) -> None:
        assert "trade_frequency_guard" not in _warn_names(_dna(daily_trade_frequency_limit=200))

    def test_201_trades_warn(self) -> None:
        assert "trade_frequency_guard" in _warn_names(_dna(daily_trade_frequency_limit=201), mode="sim")

    def test_frequency_warn_not_fatal(self) -> None:
        dna = _dna(daily_trade_frequency_limit=1000)
        violations = _audit(dna, mode="sim")
        freq_vs = [v for v in violations if v.principle_name == "trade_frequency_guard"]
        assert freq_vs
        assert all(v.severity == "warn" for v in freq_vs)


# ---------------------------------------------------------------------------
# Cross-principle: combined attack
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCombinedAttacks:

    def test_max_harm_dna_triggers_many_fatals(self) -> None:
        """A DNA crafted for maximum harm must trigger ≥ 8 fatal violations."""
        evil_dna = json.dumps({
            "hyperparam_suggestion": {
                "max_risk_percent": 50.0,
                "drawdown_kill_percent": 100.0,
                "kelly_fraction": 1.0,
                "daily_loss_cap": 99999.0,
                "leverage_multiplier": 20.0,
            },
            "disable_risk_controller": True,
            "bypass_order_gatekeeper": True,
            "mutation_depth": "radical",
            "approval_required": False,
            "skip_human_approval": True,
            "aggressive_evolution": True,
            "disable_circuit_breaker": True,
            "bypass_session_guard": True,
            "neuroevolution": {"require_real_simulator_data": False},
        })
        fatals = _fatal_names(evil_dna, mode="real")
        assert len(fatals) >= 8, f"Expected ≥ 8 fatals, got: {fatals}"

    def test_is_clean_returns_false_for_evil_dna(self) -> None:
        evil_dna = _dna(disable_risk_controller=True)
        assert not TRADING_CONSTITUTION.is_clean(evil_dna, mode="sim")

    def test_is_clean_returns_true_for_clean_dna(self) -> None:
        assert TRADING_CONSTITUTION.is_clean(_MINIMAL_VALID_DNA, mode="sim")

    def test_raise_on_fatal_raises_violation_error(self) -> None:
        evil = _dna(disable_risk_controller=True)
        with pytest.raises(ConstitutionalViolationError) as exc_info:
            TRADING_CONSTITUTION.audit(evil, mode="sim", raise_on_fatal=True)
        assert exc_info.value.violations


# ---------------------------------------------------------------------------
# probe_attack helper
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestProbeAttack:

    def test_probe_attack_detects_expected_violation(self) -> None:
        dna = _dna(disable_risk_controller=True)
        result = TRADING_CONSTITUTION.probe_attack(
            dna, mode="sim", expected_violations=["no_naked_orders"]
        )
        assert result["blocked"] is True
        assert result["expected_hit"] is True
        assert result["missed_violations"] == []

    def test_probe_attack_reports_missed(self) -> None:
        dna = _dna(disable_risk_controller=True)
        result = TRADING_CONSTITUTION.probe_attack(
            dna, mode="sim", expected_violations=["no_naked_orders", "no_such_principle"]
        )
        assert "no_such_principle" in result["missed_violations"]


# ---------------------------------------------------------------------------
# _parse_dna_content edge cases
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestParseDnaContent:

    def test_empty_string_returns_validation_sentinel(self) -> None:
        assert _parse_dna_content("") == {"__dna_validation_error__": "empty_or_non_string"}

    def test_plain_text_returns_validation_sentinel(self) -> None:
        assert _parse_dna_content("be conservative") == {"__dna_validation_error__": "non_json_payload"}

    def test_valid_json_returns_dict(self) -> None:
        assert _parse_dna_content('{"a": 1}') == {"a": 1}

    def test_invalid_json_returns_validation_sentinel(self) -> None:
        assert _parse_dna_content("{broken json") == {"__dna_validation_error__": "json_parse_error"}

    def test_json_list_returns_validation_sentinel(self) -> None:
        assert _parse_dna_content("[1,2,3]") == {"__dna_validation_error__": "non_json_payload"}

    def test_none_returns_validation_sentinel(self) -> None:
        assert _parse_dna_content(None) == {"__dna_validation_error__": "empty_or_non_string"}  # type: ignore[arg-type]
