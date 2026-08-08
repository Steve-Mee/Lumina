"""Admin dashboard panel builders + Dash start_dashboard.

Extracted from ``admin_endpoints_core`` (Wave B2 PR-C0).
Public surface remains ``AdminEndpoints`` via the core façade.
"""
from __future__ import annotations

import logging
from typing import Any

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import threading
import time
import webbrowser
from dash import Input, Output, State, dcc, html

from lumina_core.evolution.bot_stress_choices import (
    TOOLTIP_NEURO_OHLC_NL,
    TOOLTIP_OHLC_DNA_NL,
    resolve_neuro_ohlc_stress_rollouts,
    resolve_ohlc_reality_stress_enabled,
    save_bot_stress_choices,
)
from lumina_core.evolution.parallel_reality_config import (
    format_tooltip_nl,
    recommend_parallel_realities,
    resolve_parallel_realities,
    save_parallel_realities_session,
)
from .state_visualizer import StateVisualizer
from .admin_dashboard_layout import AdminDashboardLayoutMixin
from .admin_dashboard_callbacks import AdminDashboardCallbacksMixin


class AdminEndpointsPanelsMixin(AdminDashboardLayoutMixin, AdminDashboardCallbacksMixin):
    """Swarm / blackboard / inference panel helpers + dashboard lifecycle."""

    @staticmethod
    def _build_empty_figure(title: str, template: str = "plotly_dark") -> go.Figure:
        return StateVisualizer.build_empty_figure(title, template)

    @staticmethod
    def _build_inference_status_lines(tracker: dict[str, Any]) -> list[str]:
        return StateVisualizer.build_inference_status_lines(tracker)

    @staticmethod
    def _build_inference_provider_figure(tracker: dict[str, Any]) -> go.Figure:
        return StateVisualizer.build_inference_provider_figure(tracker)

    def _build_swarm_figures(self) -> tuple[go.Figure, go.Figure, html.Div]:
        return self.visualizer.build_swarm_figures()

    def _build_swarm_spread_drilldown(self, click_data: dict[str, Any] | None) -> tuple[go.Figure, html.Div]:
        return self.visualizer.build_swarm_spread_drilldown(click_data)

    def _build_mode_parity_panel(self) -> html.Div:
        return self.visualizer.build_mode_parity_panel()

    def _collect_blackboard_health_state(self) -> dict[str, Any]:
        return self.metrics.collect_blackboard_health_state()

    def _record_blackboard_health_sample(self, health: dict[str, Any]) -> None:
        self.metrics.record_blackboard_health_sample(health)

    def _build_blackboard_health_panel(self, health: dict[str, Any] | None = None) -> html.Div:
        return self.visualizer.build_blackboard_health_panel(health)

    def _build_blackboard_health_trend_figure(self) -> go.Figure:
        return self.visualizer.build_blackboard_health_trend_figure()

    def _build_drawdown_distribution_figure(self) -> go.Figure:
        return self.visualizer.build_drawdown_distribution_figure()

    def start_dashboard(self) -> None:
        app = self.engine.app
        if app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        if not bool(getattr(app, "DASHBOARD_ENABLED", self.engine.config.dashboard_enabled)):
            return
        pr_recommended = int(recommend_parallel_realities())
        pr_current = int(resolve_parallel_realities())
        pr_help = format_tooltip_nl()
        ohlc_dna_on = bool(resolve_ohlc_reality_stress_enabled())
        neuro_roll_on = bool(resolve_neuro_ohlc_stress_rollouts())
        stress_check_val: list[str] = []
        if ohlc_dna_on:
            stress_check_val.append("dna")
        if neuro_roll_on:
            stress_check_val.append("neuro")
        dash_app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
        dash_app.layout = self._build_admin_dashboard_layout(
            pr_current=pr_current,
            pr_recommended=pr_recommended,
            pr_help=pr_help,
            stress_check_val=stress_check_val,
        )
        self._register_admin_dashboard_callbacks(dash_app, app)
        setattr(app, "dash_app", dash_app)
        print("Dashboard gestart -> http://127.0.0.1:8050  (met kosten, resultaat en procentuele vergelijking)")
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        logging.getLogger("werkzeug.serving").setLevel(logging.ERROR)
        logging.getLogger("dash.dash").setLevel(logging.WARNING)
        webbrowser.open("http://127.0.0.1:8050")
        try:
            dash_app.run(debug=False, port=8050, use_reloader=False)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/admin_endpoints_core.py:769")
            dash_app.run_server(debug=False, port=8050, use_reloader=False)
