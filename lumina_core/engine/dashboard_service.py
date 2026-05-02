from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import plotly.graph_objects as go
from dash import html

from .admin_endpoints import AdminEndpoints
from .lumina_engine import LuminaEngine
from .metrics_collector import MetricsCollector
from .state_visualizer import StateVisualizer


@dataclass
class DashboardService:
    """Dashboard and performance analytics service backed by engine state."""

    engine: LuminaEngine
    visualization_service: Any | None = None
    _metrics: MetricsCollector = field(init=False, repr=False)
    _visualizer: StateVisualizer = field(init=False, repr=False)
    _admin: AdminEndpoints = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("DashboardService requires a LuminaEngine")
        self._metrics = MetricsCollector(engine=self.engine)
        self._visualizer = StateVisualizer(engine=self.engine, metrics=self._metrics)
        self._admin = AdminEndpoints(
            engine=self.engine,
            metrics=self._metrics,
            visualizer=self._visualizer,
            visualization_service=self.visualization_service,
        )

    @property
    def blackboard_health_history(self) -> Any:
        return self._metrics.blackboard_health_history

    def update_performance_log(self, trade_data: dict[str, Any]) -> None:
        self._metrics.update_performance_log(trade_data)

    def generate_strategy_heatmap(self) -> Any:
        return self._metrics.generate_strategy_heatmap()

    def generate_performance_summary(self) -> dict[str, Any]:
        return self._metrics.generate_performance_summary()

    @staticmethod
    def _build_empty_figure(title: str, template: str = "plotly_dark") -> go.Figure:
        return StateVisualizer._build_empty_figure(title, template)

    def _build_swarm_figures(self) -> tuple[go.Figure, go.Figure, html.Div]:
        return self._visualizer._build_swarm_figures()

    def _build_swarm_spread_drilldown(self, click_data: dict[str, Any] | None) -> tuple[go.Figure, html.Div]:
        return self._visualizer._build_swarm_spread_drilldown(click_data)

    @staticmethod
    def _build_inference_status_lines(tracker: dict[str, Any]) -> list[str]:
        return StateVisualizer._build_inference_status_lines(tracker)

    @staticmethod
    def _build_inference_provider_figure(tracker: dict[str, Any]) -> go.Figure:
        return StateVisualizer._build_inference_provider_figure(tracker)

    @staticmethod
    def _sum_metric(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float:
        return MetricsCollector._sum_metric(snapshot, metric_name, labels=labels)

    def _build_mode_parity_panel(self) -> html.Div:
        return self._visualizer._build_mode_parity_panel()

    def _classify_blackboard_health(
        self,
        *,
        blackboard_enabled: bool,
        meta_enabled: bool,
        publish_latency: float,
        reject_total: float,
        drop_total: float,
        sub_error_total: float,
        latest_conf: float,
        has_execution_event: bool,
    ) -> tuple[str, str, str]:
        return self._metrics._classify_blackboard_health(
            blackboard_enabled=blackboard_enabled,
            meta_enabled=meta_enabled,
            publish_latency=publish_latency,
            reject_total=reject_total,
            drop_total=drop_total,
            sub_error_total=sub_error_total,
            latest_conf=latest_conf,
            has_execution_event=has_execution_event,
        )

    def _collect_blackboard_health_state(self) -> dict[str, Any]:
        return self._metrics._collect_blackboard_health_state()

    def _record_blackboard_health_sample(self, health: dict[str, Any]) -> None:
        self._metrics._record_blackboard_health_sample(health)

    def _build_blackboard_health_trend_figure(self) -> go.Figure:
        return self._visualizer._build_blackboard_health_trend_figure()

    def _build_blackboard_health_panel(self, health: dict[str, Any] | None = None) -> html.Div:
        return self._visualizer._build_blackboard_health_panel(health)

    def _build_drawdown_distribution_figure(self) -> go.Figure:
        return self._visualizer._build_drawdown_distribution_figure()

    def start_dashboard(self) -> None:
        self._admin.visualization_service = self.visualization_service
        self._admin.start_dashboard()
