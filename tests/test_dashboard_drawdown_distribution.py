from __future__ import annotations

from types import SimpleNamespace

from lumina_core.engine.dashboard_service import DashboardService


class _RiskControllerStub:
    def get_status(self):
        return {
            "monte_carlo_drawdown": {
                "p50_pct": 3.4,
                "p95_pct": 7.8,
                "p99_pct": 9.6,
                "projected_max_pct": 11.2,
                "threshold_pct": 10.0,
            }
        }


def test_dashboard_drawdown_distribution_figure_contains_bars() -> None:
    engine = SimpleNamespace(
        risk_controller=_RiskControllerStub(),
        config=SimpleNamespace(blackboard_health_trend_points=20),
    )
    service = DashboardService(engine=engine)
    fig = service._build_drawdown_distribution_figure()

    assert fig is not None
    assert len(fig.data) == 1
    assert fig.data[0].type == "bar"
