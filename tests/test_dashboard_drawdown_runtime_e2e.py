from __future__ import annotations

from types import SimpleNamespace

from lumina_core.engine.dashboard_service import DashboardService
from lumina_core.engine.risk_controller import HardRiskController, RiskLimits


def test_dashboard_drawdown_panel_updates_after_runtime_snapshot() -> None:
    limits = RiskLimits(
        enforce_session_guard=False,
        runtime_mode="real",
        mc_drawdown_paths=1200,
        mc_drawdown_horizon_days=40,
        mc_drawdown_min_samples=20,
        mc_drawdown_threshold_pct=20.0,
        enable_mc_drawdown_enforce_real=True,
    )
    risk_controller = HardRiskController(limits, enforce_rules=True)
    engine = SimpleNamespace(
        risk_controller=risk_controller,
        config=SimpleNamespace(blackboard_health_trend_points=20),
    )
    service = DashboardService(engine=engine)

    fig_empty = service._build_drawdown_distribution_figure()
    assert fig_empty is not None

    for i in range(35):
        pnl = -90.0 if i % 4 == 0 else 55.0
        risk_controller.record_trade_result("MES", "TRENDING", pnl=pnl, risk_taken=100.0)

    ok, _reason, payload = risk_controller.check_monte_carlo_drawdown_pre_trade(150.0)
    assert isinstance(ok, bool)
    assert float(payload.get("projected_max_drawdown_pct", 0.0)) >= 0.0

    fig = service._build_drawdown_distribution_figure()
    assert fig is not None
    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"
    assert max(float(v) for v in fig.data[0].y) >= 0.0
