from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

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


def _figure_traces(fig: Any) -> list[Any]:
    traces = getattr(fig, "data", None)
    if traces is None:
        return []
    return list(traces)


def _trace_type(trace: Any) -> str | None:
    return getattr(trace, "type", None)


def test_dashboard_drawdown_distribution_figure_contains_bars() -> None:
    engine = SimpleNamespace(
        risk_controller=_RiskControllerStub(),
        config=SimpleNamespace(blackboard_health_trend_points=20),
    )
    service = DashboardService(engine=cast(Any, engine))
    fig = service._build_drawdown_distribution_figure()
    traces = _figure_traces(fig)

    assert fig is not None
    assert len(traces) == 1
    assert _trace_type(traces[0]) == "bar"
