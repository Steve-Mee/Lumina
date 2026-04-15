from __future__ import annotations

from lumina_core.engine.stress_suite_runner import StressSuiteRunner


def test_stress_suite_runner_returns_three_scenarios() -> None:
    runner = StressSuiteRunner()
    report = runner.build_report(
        {
            "pnl_realized": 1000.0,
            "max_drawdown": 250.0,
            "var_breach_count": 0,
        }
    )

    assert report["method"] == "deterministic_overlay_v1"
    assert "volatility_spike" in report["scenarios"]
    assert "liquidity_shock" in report["scenarios"]
    assert "correlation_breakdown" in report["scenarios"]
    assert isinstance(report["stress_ready_for_real_gate"], bool)
    assert "gate_checks" in report
    assert "gate_thresholds" in report


def test_regime_scorecard_passes_with_full_coverage() -> None:
    runner = StressSuiteRunner()
    stress = {
        "stress_ready_for_real_gate": True,
    }
    regime_results = {
        "TRENDING": {"trades": 30, "winrate": 0.52, "sharpe": 0.9, "maxdd": 800.0},
        "RANGING": {"trades": 28, "winrate": 0.49, "sharpe": 0.6, "maxdd": 900.0},
        "VOLATILE": {"trades": 22, "winrate": 0.40, "sharpe": 0.2, "maxdd": 1400.0},
        "ROLLOVER": {"trades": 12, "winrate": 0.35, "sharpe": -0.05, "maxdd": 1500.0},
    }

    card = runner.build_regime_scorecard(regime_results, stress)

    assert card["overall_pass"] is True
    assert card["promotion_advice"] == "promote_candidate"
    assert card["missing_regimes"] == []


def test_regime_scorecard_fails_when_regime_missing_or_stress_fails() -> None:
    runner = StressSuiteRunner()
    pack = runner.build_validation_pack(
        {"pnl_realized": 500.0, "max_drawdown": 200.0, "var_breach_count": 1},
        {
            "TRENDING": {"trades": 30, "winrate": 0.52, "sharpe": 0.9, "maxdd": 800.0},
            "RANGING": {"trades": 28, "winrate": 0.49, "sharpe": 0.6, "maxdd": 900.0},
        },
    )

    scorecard = pack["regime_scorecard"]
    assert scorecard["overall_pass"] is False
    assert "HIGH_VOLATILITY" in scorecard["missing_regimes"]
    assert scorecard["promotion_advice"] == "hold_and_retrain"
    assert "gate_failure_reasons" in scorecard


def test_stress_report_exposes_explicit_gate_failure_reason() -> None:
    runner = StressSuiteRunner()
    report = runner.build_report(
        {
            "pnl_realized": 1000.0,
            "max_drawdown": 250.0,
            "var_breach_count": 1,
        }
    )

    assert report["stress_ready_for_real_gate"] is False
    assert report["gate_checks"]["var_breach_limit"] is False
    reasons = report["gate_fail_reasons"]
    assert isinstance(reasons, list)
    assert any("VAR_BREACH_LIMIT_EXCEEDED" in item for item in reasons)
