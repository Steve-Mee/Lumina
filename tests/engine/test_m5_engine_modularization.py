"""M5 engine modularization LOC guards."""

from __future__ import annotations

from pathlib import Path

import pytest

_ENG = Path(__file__).resolve().parents[2] / "lumina_core" / "engine"
_LOC_LIMIT = 400

_MODULES = [
    "agent_blackboard.py",
    "agent_blackboard_types.py",
    "agent_blackboard_publish.py",
    "agent_blackboard_metrics.py",
    "reasoning_paths.py",
    "reasoning_paths_latency.py",
    "reasoning_paths_infer_head.py",
    "reasoning_paths_infer_tail.py",
    "operations_service.py",
    "operations_service_orders.py",
    "operations_service_market.py",
    "admin_dashboard_layout.py",
    "admin_dashboard_layout_build.py",
    "state_visualizer.py",
    "state_visualizer_swarm.py",
    "state_visualizer_inference.py",
    "state_visualizer_health.py",
    "engine_config.py",
    "engine_config_helpers.py",
    "market_data_history_fetch.py",
    "market_data_history_helpers.py",
]


def _loc(path: Path) -> int:
    return sum(1 for _ in path.open(encoding="utf-8"))


@pytest.mark.unit
def test_m5_engine_modules_under_loc_bar() -> None:
    for name in _MODULES:
        path = _ENG / name
        assert path.is_file(), name
        n = _loc(path)
        assert n <= _LOC_LIMIT, f"{name} LOC {n} > {_LOC_LIMIT}"


@pytest.mark.unit
def test_m5_engine_public_apis() -> None:
    from lumina_core.engine.admin_dashboard_layout import AdminDashboardLayoutMixin
    from lumina_core.engine.agent_blackboard import AgentBlackboard, BlackboardEvent
    from lumina_core.engine.operations_service import OperationsService
    from lumina_core.engine.reasoning_paths import ReasoningPathsMixin

    assert hasattr(AgentBlackboard, "publish_sync")
    assert hasattr(AgentBlackboard, "subscribe")
    assert BlackboardEvent is not None
    assert hasattr(ReasoningPathsMixin, "infer_json")
    assert hasattr(ReasoningPathsMixin, "_record_latency")
    assert hasattr(OperationsService, "place_order")
    assert hasattr(OperationsService, "is_market_open")
    assert hasattr(AdminDashboardLayoutMixin, "_build_admin_dashboard_layout")

    from lumina_core.engine.engine_config import EngineConfig
    from lumina_core.engine.market_data_history_fetch import MarketDataHistoryFetchMixin
    from lumina_core.engine.state_visualizer import StateVisualizer

    assert EngineConfig is not None
    assert hasattr(StateVisualizer, "build_swarm_figures")
    assert hasattr(MarketDataHistoryFetchMixin, "_fetch_historical_bars")
