"""Admin endpoints — thin façade (Wave B2 PR-C0).

Panel builders and ``start_dashboard`` live in ``admin_endpoints_panels``.
Public imports remain stable via ``admin_endpoints`` / this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .admin_endpoints_panels import AdminEndpointsPanelsMixin
from .metrics_collector import MetricsCollectorProtocol
from .state_visualizer import StateVisualizerProtocol


class AdminEndpointsProtocol(Protocol):
    visualization_service: Any | None

    def start_dashboard(self) -> None: ...


@dataclass
class AdminEndpoints(AdminEndpointsPanelsMixin):
    engine: Any
    metrics: MetricsCollectorProtocol
    visualizer: StateVisualizerProtocol
    visualization_service: Any | None = None

    def generate_strategy_heatmap(self) -> Any:
        return self.metrics.generate_strategy_heatmap()

    def generate_performance_summary(self) -> dict[str, Any]:
        return self.metrics.generate_performance_summary()


__all__ = ["AdminEndpoints", "AdminEndpointsProtocol", "AdminEndpointsPanelsMixin"]
