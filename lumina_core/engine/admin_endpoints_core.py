from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any, Protocol
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
from .metrics_collector import MetricsCollectorProtocol
from .state_visualizer import StateVisualizer, StateVisualizerProtocol


class AdminEndpointsProtocol(Protocol):
    visualization_service: Any | None

    def start_dashboard(self) -> None: ...


@dataclass
class AdminEndpoints:
    engine: Any
    metrics: MetricsCollectorProtocol
    visualizer: StateVisualizerProtocol
    visualization_service: Any | None = None

    def generate_strategy_heatmap(self) -> Any:
        return self.metrics.generate_strategy_heatmap()

    def generate_performance_summary(self) -> dict[str, Any]:
        return self.metrics.generate_performance_summary()

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
        dash_app.layout = dbc.Container(
            [
                html.H1(
                    "LUMINA v51 - Live Human Trading Partner",
                    style={"textAlign": "center", "color": "#00ff88", "marginBottom": "20px"},
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.H5(
                                                    "Evolutie — parallelle stress-universa (multi-reality SIM)",
                                                    className="text-muted",
                                                ),
                                                html.P(
                                                    [
                                                        f"Actief in dit proces: {pr_current}  ·  "
                                                        f"Aanbevolen op jouw PC (CPU): {pr_recommended}  (laag houdt "
                                                        f"de belasting beperkt). ",
                                                        html.Span(
                                                            "ⓘ",
                                                            id="parallel-realities-tooltip-target",
                                                            style={
                                                                "cursor": "help",
                                                                "color": "#7fd4ff",
                                                                "fontWeight": "800",
                                                                "marginLeft": "4px",
                                                            },
                                                            title=pr_help[:220] + "…",
                                                        ),
                                                    ],
                                                    style={"fontSize": "14px", "color": "#c8d0dc"},
                                                ),
                                                dbc.Tooltip(
                                                    pr_help,
                                                    target="parallel-realities-tooltip-target",
                                                    placement="bottom",
                                                    style={"maxWidth": "520px", "whiteSpace": "pre-line"},
                                                ),
                                                dbc.Row(
                                                    [
                                                        dbc.Col(
                                                            [
                                                                html.Label(
                                                                    "Aantal (min 1 — max 50):",
                                                                    style={"color": "#bbbbbb", "fontSize": "13px"},
                                                                ),
                                                                dcc.Input(
                                                                    id="parallel-realities-input",
                                                                    type="number",
                                                                    min=1,
                                                                    max=50,
                                                                    step=1,
                                                                    value=pr_current,
                                                                    debounce=True,
                                                                    style={
                                                                        "width": "100px",
                                                                        "fontSize": "16px",
                                                                        "padding": "4px 8px",
                                                                        "borderRadius": "6px",
                                                                    },
                                                                ),
                                                            ],
                                                            width="auto",
                                                        ),
                                                        dbc.Col(
                                                            [
                                                                dbc.Button(
                                                                    "Keuze opslaan",
                                                                    id="parallel-realities-save",
                                                                    color="info",
                                                                    size="sm",
                                                                    n_clicks=0,
                                                                    className="mt-3",
                                                                ),
                                                            ],
                                                            width="auto",
                                                        ),
                                                    ],
                                                    className="g-2 align-items-end",
                                                ),
                                                html.Div(
                                                    id="parallel-realities-feedback",
                                                    style={"minHeight": "24px", "color": "#7fd4ff", "marginTop": "6px"},
                                                ),
                                                html.Hr(className="my-2", style={"borderColor": "#333"}),
                                                html.H5(
                                                    "Fase 3 — OHLC / PPO-stress (marktdata)",
                                                    className="text-muted",
                                                    style={"fontSize": "1rem", "marginTop": "6px"},
                                                ),
                                                dbc.Checklist(
                                                    id="bot-stress-checks",
                                                    options=[
                                                        {
                                                            "label": " OHLC-stress op historische ticks (DNA-evolutie) ",
                                                            "value": "dna",
                                                        },
                                                        {
                                                            "label": " PPO: meerdere OHLC-rollouts per kandidaat (zwaar) ",
                                                            "value": "neuro",
                                                        },
                                                    ],
                                                    value=stress_check_val,
                                                    switch=True,
                                                    className="mb-1",
                                                ),
                                                html.Div(
                                                    [
                                                        html.Span(
                                                            "ⓘ",
                                                            id="tooltip-ohlc-dna-target",
                                                            style={
                                                                "cursor": "help",
                                                                "color": "#7fd4ff",
                                                                "fontWeight": "800",
                                                            },
                                                        ),
                                                        dbc.Tooltip(
                                                            TOOLTIP_OHLC_DNA_NL,
                                                            target="tooltip-ohlc-dna-target",
                                                            placement="right",
                                                            style={"maxWidth": "480px", "whiteSpace": "pre-line"},
                                                        ),
                                                        html.Span("  "),
                                                        html.Span(
                                                            "ⓘ",
                                                            id="tooltip-neuro-ohlc-target",
                                                            style={
                                                                "cursor": "help",
                                                                "color": "#ffaa66",
                                                                "fontWeight": "800",
                                                            },
                                                        ),
                                                        dbc.Tooltip(
                                                            TOOLTIP_NEURO_OHLC_NL,
                                                            target="tooltip-neuro-ohlc-target",
                                                            placement="right",
                                                            style={"maxWidth": "480px", "whiteSpace": "pre-line"},
                                                        ),
                                                    ],
                                                    style={"marginBottom": "6px", "fontSize": "14px"},
                                                ),
                                                dbc.Button(
                                                    "Stress-keuzes opslaan",
                                                    id="bot-stress-save",
                                                    color="secondary",
                                                    size="sm",
                                                    n_clicks=0,
                                                    className="mb-1",
                                                ),
                                                html.Div(
                                                    id="bot-stress-feedback",
                                                    style={"minHeight": "22px", "color": "#9fd4a8", "fontSize": "13px"},
                                                ),
                                            ]
                                        )
                                    ],
                                    color="dark",
                                    outline=True,
                                )
                            ],
                            width=12,
                        ),
                    ],
                    className="mb-3",
                ),
                html.Div(
                    [
                        html.Div(id="shutdown-feedback", style={"color": "#ff8080", "fontWeight": "600"}),
                        dbc.Button("Sluit Alles", id="shutdown-btn", color="danger", n_clicks=0, className="shadow"),
                    ],
                    style={
                        "display": "flex",
                        "justifyContent": "flex-end",
                        "alignItems": "center",
                        "gap": "12px",
                        "position": "fixed",
                        "top": "12px",
                        "right": "4px",
                        "zIndex": 99999,
                        "background": "rgba(0, 0, 0, 0.72)",
                        "padding": "8px 10px",
                        "borderRadius": "10px",
                    },
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.H5("API Kosten Vandaag", className="text-muted text-center"),
                                                html.H2(
                                                    id="cost-meter",
                                                    className="text-center",
                                                    style={"fontSize": "42px", "fontWeight": "bold"},
                                                ),
                                            ]
                                        )
                                    ],
                                    color="dark",
                                    outline=True,
                                )
                            ],
                            width=3,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.H5("Netto Resultaat Vandaag", className="text-muted text-center"),
                                                html.H2(
                                                    id="pnl-meter",
                                                    className="text-center",
                                                    style={"fontSize": "42px", "fontWeight": "bold"},
                                                ),
                                            ]
                                        )
                                    ],
                                    color="dark",
                                    outline=True,
                                )
                            ],
                            width=3,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.H5(
                                                    "Kosten als % van Resultaat", className="text-muted text-center"
                                                ),
                                                html.H2(
                                                    id="percentage-meter",
                                                    className="text-center",
                                                    style={"fontSize": "42px", "fontWeight": "bold"},
                                                ),
                                            ]
                                        )
                                    ],
                                    color="dark",
                                    outline=True,
                                )
                            ],
                            width=3,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.H5("Cache Hits Vandaag", className="text-muted text-center"),
                                                html.H2(
                                                    id="cache-meter",
                                                    className="text-center",
                                                    style={"fontSize": "42px", "fontWeight": "bold"},
                                                ),
                                            ]
                                        )
                                    ],
                                    color="dark",
                                    outline=True,
                                )
                            ],
                            width=3,
                        ),
                    ],
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.H5("Inference Provider", className="text-muted text-center"),
                                                html.H2(
                                                    id="inference-provider-meter",
                                                    className="text-center",
                                                    style={"fontSize": "34px", "fontWeight": "bold"},
                                                ),
                                            ]
                                        )
                                    ],
                                    color="dark",
                                    outline=True,
                                )
                            ],
                            width=4,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.H5("Inference Avg Latency", className="text-muted text-center"),
                                                html.H2(
                                                    id="inference-latency-meter",
                                                    className="text-center",
                                                    style={"fontSize": "34px", "fontWeight": "bold"},
                                                ),
                                            ]
                                        )
                                    ],
                                    color="dark",
                                    outline=True,
                                )
                            ],
                            width=4,
                        ),
                        dbc.Col(
                            [
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            [
                                                html.H5("Inference Failures", className="text-muted text-center"),
                                                html.H2(
                                                    id="inference-fail-meter",
                                                    className="text-center",
                                                    style={"fontSize": "34px", "fontWeight": "bold"},
                                                ),
                                            ]
                                        )
                                    ],
                                    color="dark",
                                    outline=True,
                                )
                            ],
                            width=4,
                        ),
                    ],
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col([dcc.Graph(id="live-chart")], width=8),
                        dbc.Col(
                            [
                                html.H5("Account Status & Equity Curve"),
                                html.Div(id="status-panel", style={"fontSize": "18px", "color": "#0ff"}),
                                dcc.Graph(id="equity-curve"),
                            ],
                            width=4,
                        ),
                    ]
                ),
                dbc.Row(
                    [
                        dbc.Col([dcc.Graph(id="inference-provider-figure")], width=12),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col([html.H5("Swarm Correlation Matrix"), dcc.Graph(id="swarm-correlation")], width=6),
                        dbc.Col([html.H5("Swarm Allocation"), dcc.Graph(id="swarm-allocation")], width=4),
                        dbc.Col(
                            [
                                html.H5("Regime Consensus"),
                                html.Div(id="swarm-regime-panel", style={"fontSize": "15px", "color": "#ddd"}),
                            ],
                            width=2,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col([html.H5("Pair Spread Drill-down"), dcc.Graph(id="swarm-spread-drilldown")], width=9),
                        dbc.Col(
                            [
                                html.H5("Pair Detail"),
                                html.Div(id="swarm-spread-detail", style={"fontSize": "15px", "color": "#ddd"}),
                            ],
                            width=3,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.H5("Mode Parity"),
                                html.Div(id="mode-parity-panel", style={"fontSize": "15px", "color": "#ddd"}),
                            ],
                            width=6,
                        ),
                        dbc.Col(
                            [
                                html.H5("Blackboard Health"),
                                html.Div(id="blackboard-health-panel", style={"fontSize": "15px", "color": "#ddd"}),
                                dcc.Graph(id="blackboard-health-trend"),
                            ],
                            width=6,
                        ),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col([html.H5("Drawdown Distribution"), dcc.Graph(id="drawdown-distribution")], width=12),
                    ],
                    className="mb-3",
                ),
                html.H5("Strategy Heatmap - Winrate per Regime"),
                dcc.Graph(id="heatmap"),
                html.H5("Laatste Trades & Reflections"),
                dbc.Table(id="trade-table", bordered=True, color="dark"),
                dbc.Modal(
                    [
                        dbc.ModalHeader("Afsluiten bevestigen"),
                        dbc.ModalBody("Weet je zeker dat je LUMINA volledig wilt afsluiten?"),
                        dbc.ModalFooter(
                            [
                                dbc.Button("Annuleren", id="shutdown-cancel-btn", className="ms-auto", n_clicks=0),
                                dbc.Button("Afsluiten", id="shutdown-confirm-btn", color="danger", n_clicks=0),
                            ]
                        ),
                    ],
                    id="shutdown-modal",
                    centered=True,
                    is_open=False,
                ),
                dcc.Interval(id="interval", interval=8000, n_intervals=0),
            ],
            fluid=True,
        )

        @dash_app.callback(
            Output("parallel-realities-feedback", "children"),
            Input("parallel-realities-save", "n_clicks"),
            State("parallel-realities-input", "value"),
            prevent_initial_call=True,
        )
        def _save_parallel_realities(n_clicks: int, value: int | float | str | None) -> str:  # type: ignore[untyped-decorator]
            if not n_clicks:
                return ""
            try:
                raw = int(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return "Ongeldig getal; kies 1—50."
            n = save_parallel_realities_session(raw)
            return f"Opgeslagen: {n} stress-universa (actief in dit Lumina-proces; herstart de bot om overal 100% zeker dezelfde waarde te gebruiken)."

        @dash_app.callback(
            Output("bot-stress-feedback", "children"),
            Input("bot-stress-save", "n_clicks"),
            State("bot-stress-checks", "value"),
            prevent_initial_call=True,
        )
        def _save_bot_stress_choices_dash(n_clicks: int, values: list[str] | None) -> str:  # type: ignore[untyped-decorator]
            if not n_clicks:
                return ""
            v = list(values or [])
            dna = "dna" in v
            neuro = "neuro" in v
            save_bot_stress_choices(
                ohlc_reality_stress_enabled=bool(dna),
                use_ohlc_stress_rollouts=bool(neuro),
            )
            return (
                f"Opgeslagen: DNA-OHLC={'aan' if dna else 'uit'}, PPO-OHLC-rollouts={'aan' if neuro else 'uit'} "
                "(actief in dit proces; `state/bot_stress_choices.json`)."
            )

        @dash_app.callback(
            [
                Output("live-chart", "figure"),
                Output("equity-curve", "figure"),
                Output("status-panel", "children"),
                Output("trade-table", "children"),
                Output("heatmap", "figure"),
                Output("cost-meter", "children"),
                Output("pnl-meter", "children"),
                Output("percentage-meter", "children"),
                Output("cache-meter", "children"),
                Output("inference-provider-meter", "children"),
                Output("inference-latency-meter", "children"),
                Output("inference-fail-meter", "children"),
                Output("cost-meter", "style"),
                Output("pnl-meter", "style"),
                Output("percentage-meter", "style"),
                Output("cache-meter", "style"),
                Output("inference-provider-meter", "style"),
                Output("inference-latency-meter", "style"),
                Output("inference-fail-meter", "style"),
                Output("inference-provider-figure", "figure"),
                Output("swarm-correlation", "figure"),
                Output("swarm-allocation", "figure"),
                Output("swarm-regime-panel", "children"),
                Output("mode-parity-panel", "children"),
                Output("blackboard-health-panel", "children"),
                Output("blackboard-health-trend", "figure"),
                Output("drawdown-distribution", "figure"),
            ],
            Input("interval", "n_intervals"),
        )
        def update_dashboard(
            _: int,
        ) -> tuple[
            go.Figure,
            go.Figure,
            html.Div,
            list[Any],
            go.Figure,
            str,
            str,
            str,
            str,
            str,
            str,
            str,
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
            dict[str, Any],
            go.Figure,
            go.Figure,
            go.Figure,
            html.Div,
            html.Div,
            html.Div,
            go.Figure,
            go.Figure,
        ]:  # type: ignore[untyped-decorator]
            chart_base64 = None
            now_ts = time.time()
            if self.visualization_service is not None and now_ts - self.engine.dashboard_last_chart_ts >= int(
                self.engine.config.dashboard_chart_refresh_sec
            ):
                chart_base64 = self.visualization_service.generate_multi_tf_chart(self.engine.AI_DRAWN_FIBS)
                self.engine.dashboard_last_has_image = bool(chart_base64)
                self.engine.dashboard_last_chart_ts = now_ts
            fig_chart = go.Figure()
            if chart_base64 or self.engine.dashboard_last_has_image:
                fig_chart.add_annotation(text="Live AI Chart (zie screen-share venster)", showarrow=False)
            fig_equity = go.Figure(data=go.Scatter(y=self.engine.equity_curve, mode="lines", name="Equity"))
            fig_equity.update_layout(title="Equity Curve", template="plotly_dark")
            dream_snapshot = self.engine.get_current_dream_snapshot()
            trade_mode = self.engine.config.trade_mode.upper()
            table_header = [html.Thead(html.Tr([html.Th("Tijd"), html.Th("Signal"), html.Th("PnL"), html.Th("Conf")]))]
            rows = [
                html.Tr(
                    [
                        html.Td(t.get("ts", "")),
                        html.Td(t.get("signal", "")),
                        html.Td(f"${t.get('pnl', 0):,.0f}"),
                        html.Td(f"{t.get('confluence', 0):.2f}"),
                    ]
                )
                for t in self.engine.trade_log[-10:]
            ]
            table_body = [html.Tbody(rows)]
            heatmap_fig = self.generate_strategy_heatmap() or go.Figure()
            tracker = self.engine.cost_tracker
            cost_today = float(tracker.get("today", 0.0))
            pnl_today = self.engine.realized_pnl_today + self.engine.open_pnl
            inference_lines = self._build_inference_status_lines(tracker)
            status = html.Div(
                [
                    html.P(f"Mode: {trade_mode} | Equity: ${self.engine.account_equity:,.0f}"),
                    html.P(
                        f"Open PnL: ${self.engine.open_pnl:,.0f} | Realized PnL: ${self.engine.realized_pnl_today:,.0f}"
                    ),
                    html.P(
                        f"Current Dream: {dream_snapshot.get('chosen_strategy')} -> {dream_snapshot.get('signal')} (conf {dream_snapshot.get('confluence_score', 0):.2f})"
                    ),
                    html.P(inference_lines[0], style={"color": "#7fd4ff"}),
                    html.P(inference_lines[1], style={"color": "#bbbbbb"}),
                    html.P(inference_lines[2], style={"color": "#ffc857"}) if len(inference_lines) > 2 else html.Div(),
                ]
            )
            if pnl_today > 0:
                percentage = (cost_today / abs(pnl_today)) * 100
                perc_text = f"{percentage:.1f}%"
                perc_color = "#00ff88" if percentage < 8 else "#ff4444"
            else:
                perc_text = "N/A"
                perc_color = "#aaaaaa"
            cost_color = "#ffaa00" if cost_today < 50 else "#ff4444"
            cost_text = f"${cost_today:.2f}"
            pnl_color = "#00ff88" if pnl_today >= 0 else "#ff4444"
            pnl_text = f"${pnl_today:,.0f}"
            cache_hits = int(tracker.get("cached_analyses", 0))
            cache_color = "#00d4ff" if cache_hits > 0 else "#888888"
            inference_provider = str(tracker.get("local_inference_last_provider") or "pending")
            inference_requests = int(tracker.get("local_inference_requests", 0))
            total_inference_latency = float(tracker.get("local_inference_latency_ms_total", 0.0))
            inference_avg_latency = total_inference_latency / inference_requests if inference_requests > 0 else 0.0
            inference_failures = int(tracker.get("local_inference_failures", 0))
            inference_provider_color = "#7fd4ff" if inference_provider != "pending" else "#888888"
            inference_latency_color = (
                "#00ff88" if inference_avg_latency < 900 else "#ffc857" if inference_avg_latency < 2500 else "#ff4444"
            )
            inference_failure_color = "#00ff88" if inference_failures == 0 else "#ff4444"
            inference_history_fig = self._build_inference_provider_figure(tracker)
            swarm_corr_fig, swarm_alloc_fig, swarm_regime_panel = self._build_swarm_figures()
            mode_parity_panel = self._build_mode_parity_panel()
            blackboard_health = self._collect_blackboard_health_state()
            self._record_blackboard_health_sample(blackboard_health)
            blackboard_health_panel = self._build_blackboard_health_panel(blackboard_health)
            blackboard_health_trend = self._build_blackboard_health_trend_figure()
            drawdown_distribution_fig = self._build_drawdown_distribution_figure()
            return (
                fig_chart,
                fig_equity,
                status,
                table_header + table_body,
                heatmap_fig,
                cost_text,
                pnl_text,
                perc_text,
                f"{cache_hits}",
                inference_provider,
                f"{inference_avg_latency:.1f} ms",
                str(inference_failures),
                {"color": cost_color, "fontSize": "42px", "fontWeight": "bold"},
                {"color": pnl_color, "fontSize": "42px", "fontWeight": "bold"},
                {"color": perc_color, "fontSize": "42px", "fontWeight": "bold"},
                {"color": cache_color, "fontSize": "42px", "fontWeight": "bold"},
                {"color": inference_provider_color, "fontSize": "34px", "fontWeight": "bold"},
                {"color": inference_latency_color, "fontSize": "34px", "fontWeight": "bold"},
                {"color": inference_failure_color, "fontSize": "34px", "fontWeight": "bold"},
                inference_history_fig,
                swarm_corr_fig,
                swarm_alloc_fig,
                swarm_regime_panel,
                mode_parity_panel,
                blackboard_health_panel,
                blackboard_health_trend,
                drawdown_distribution_fig,
            )

        @dash_app.callback(
            [
                Output("swarm-spread-drilldown", "figure"),
                Output("swarm-spread-detail", "children"),
            ],
            [
                Input("swarm-correlation", "clickData"),
                Input("interval", "n_intervals"),
            ],
        )
        def update_spread_drilldown(click_data: dict[str, Any] | None, _: int) -> tuple[go.Figure, html.Div]:  # type: ignore[untyped-decorator]
            return self._build_swarm_spread_drilldown(click_data)

        @dash_app.callback(
            Output("shutdown-modal", "is_open"),
            Input("shutdown-btn", "n_clicks"),
            Input("shutdown-cancel-btn", "n_clicks"),
            Input("shutdown-confirm-btn", "n_clicks"),
            prevent_initial_call=True,
        )
        def toggle_shutdown_modal(open_clicks: int, cancel_clicks: int, confirm_clicks: int) -> bool:  # type: ignore[untyped-decorator]
            if cancel_clicks > 0 or (open_clicks == 0 and confirm_clicks == 0):
                return False
            if open_clicks > 0:
                return True
            return False

        @dash_app.callback(
            Output("shutdown-feedback", "children"),
            Input("shutdown-confirm-btn", "n_clicks"),
            prevent_initial_call=True,
        )
        def execute_shutdown(confirm_clicks: int) -> str:  # type: ignore[untyped-decorator]
            if confirm_clicks > 0:
                print(f"[{time.strftime('%H:%M:%S')}] 🛑 Shutdown button confirmed from dashboard")
                threading.Thread(target=app.emergency_stop, daemon=False).start()
                return "App wordt afgesloten..."
            return ""

        setattr(app, "dash_app", dash_app)
        print("🌐 Dashboard gestart -> http://127.0.0.1:8050  (met kosten, resultaat en procentuele vergelijking)")
        webbrowser.open("http://127.0.0.1:8050")
        try:
            dash_app.run(debug=False, port=8050, use_reloader=False)
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/admin_endpoints_core.py:769")
            dash_app.run_server(debug=False, port=8050, use_reloader=False)
