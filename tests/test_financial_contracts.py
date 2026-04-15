from __future__ import annotations

from lumina_core.engine.financial_contracts import (
    FinancialReportingContract,
    MarginSnapshotContract,
    StressSuiteContract,
    VaRQualityContract,
)


def test_financial_contracts_instantiation() -> None:
    margin = MarginSnapshotContract(
        source="config_snapshot",
        as_of="2026-04-15T00:00:00+00:00",
        confidence=0.8,
        stale_after_hours=168,
        stale=False,
    )
    var_quality = VaRQualityContract(
        quality_score=82.5,
        quality_band="green",
        data_points=64,
        effective_max_var_usd=1200.0,
        effective_max_total_open_risk=3000.0,
    )
    reporting = FinancialReportingContract(
        learning_label="Learning Fitness (niet productie-benchmark)",
        realism_label="Realism Adjusted (wel vergelijkbaar voor live readiness)",
        metrics_for_readiness_gate="realism",
        parity_delta_pnl_realized=120.5,
        parity_delta_max_drawdown=-25.0,
        parity_delta_sharpe_annualized=0.221,
    )
    stress = StressSuiteContract(
        method="deterministic_overlay_v1",
        worst_case_drawdown=500.0,
        worst_case_var_breach_count=2,
        stress_ready_for_real_gate=True,
    )

    assert margin.source == "config_snapshot"
    assert var_quality.quality_band == "green"
    assert reporting.metrics_for_readiness_gate == "realism"
    assert stress.stress_ready_for_real_gate is True
