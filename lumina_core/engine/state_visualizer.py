from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import plotly.graph_objects as go
from dash import html

from .metrics_collector import MetricsCollectorProtocol


class StateVisualizerProtocol(Protocol):
    def build_swarm_figures(self) -> tuple[go.Figure, go.Figure, html.Div]: ...

    def build_swarm_spread_drilldown(self, click_data: dict[str, Any] | None) -> tuple[go.Figure, html.Div]: ...

    def build_mode_parity_panel(self) -> html.Div: ...

    def build_blackboard_health_trend_figure(self) -> go.Figure: ...

    def build_blackboard_health_panel(self, health: dict[str, Any] | None = None) -> html.Div: ...

    def build_drawdown_distribution_figure(self) -> go.Figure: ...

    @staticmethod
    def build_empty_figure(title: str, template: str = "plotly_dark") -> go.Figure: ...

    @staticmethod
    def build_inference_status_lines(tracker: dict[str, Any]) -> list[str]: ...

    @staticmethod
    def build_inference_provider_figure(tracker: dict[str, Any]) -> go.Figure: ...


class _MetricSumming(Protocol):
    @staticmethod
    def sum_metric(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float: ...


class _HealthCollector(Protocol):
    def collect_blackboard_health_state(self) -> dict[str, Any]: ...


class _HealthHistory(Protocol):
    blackboard_health_history: Any


class _VisualizerMetrics(MetricsCollectorProtocol, _MetricSumming, _HealthCollector, _HealthHistory, Protocol):
    pass


from lumina_core.engine.state_visualizer_swarm import StateVisualizerSwarmMixin
from lumina_core.engine.state_visualizer_inference import StateVisualizerInferenceMixin
from lumina_core.engine.state_visualizer_health import StateVisualizerHealthMixin

class StateVisualizer(
    StateVisualizerSwarmMixin,
    StateVisualizerInferenceMixin,
    StateVisualizerHealthMixin,
):
    def __init__(self, engine: Any, metrics: _VisualizerMetrics) -> None:
        self.engine = engine
        self.metrics = metrics

    @staticmethod
    def _sum_metric(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float:
        return float(StateVisualizer._metrics_sum(snapshot, metric_name, labels=labels))

    @staticmethod
    def _metrics_sum(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float:
        from .metrics_collector import MetricsCollector

        return MetricsCollector.sum_metric(snapshot, metric_name, labels=labels)


