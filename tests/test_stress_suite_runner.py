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
