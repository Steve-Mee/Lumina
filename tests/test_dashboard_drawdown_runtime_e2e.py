from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from lumina_core.engine.dashboard_service import DashboardService
from lumina_core.risk.risk_controller import HardRiskController, RiskLimits


def _figure_traces(fig: Any) -> list[Any]:
    traces = getattr(fig, "data", None)
    if traces is None:
        return []
    return list(traces)


def _trace_type(trace: Any) -> str | None:
    return getattr(trace, "type", None)


def _trace_y_values(trace: Any) -> list[float]:
    values = getattr(trace, "y", None)
    if values is None:
        return []
    return [float(value) for value in values]


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
    service = DashboardService(engine=cast(Any, engine))

    fig_empty = service._build_drawdown_distribution_figure()
    assert fig_empty is not None

    for i in range(35):
        pnl = -90.0 if i % 4 == 0 else 55.0
        risk_controller.record_trade_result("MES", "TRENDING", pnl=pnl, risk_taken=100.0)

    ok, _reason, payload = risk_controller.check_monte_carlo_drawdown_pre_trade(150.0)
    projected_raw = payload.get("projected_max_drawdown_pct", 0.0)
    assert isinstance(ok, bool)
    assert isinstance(projected_raw, (int, float, str, bool))
    assert float(projected_raw) >= 0.0

    fig = service._build_drawdown_distribution_figure()
    traces = _figure_traces(fig)
    assert fig is not None
    assert len(traces) == 1
    assert _trace_type(traces[0]) == "bar"
    assert max(_trace_y_values(traces[0])) >= 0.0
