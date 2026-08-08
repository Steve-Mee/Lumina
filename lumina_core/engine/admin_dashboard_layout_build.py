"""Admin dashboard layout tree (M5 reconstruct — source recovered after accidental overwrite).

Provides component IDs required by ``admin_dashboard_callbacks``.
"""
from __future__ import annotations


import dash_bootstrap_components as dbc
from dash import dcc, html


class AdminDashboardLayoutBuildMixin:
    """Builds the Dash layout for the admin cockpit."""

    def _build_admin_dashboard_layout(
        self,
        *,
        pr_current: int,
        pr_recommended: int,
        pr_help: str,
        stress_check_val: list[str],
    ) -> html.Div:
        empty_fig = self._build_empty_figure("Waiting for data…")
        return html.Div(
            [
                dcc.Interval(id="interval", interval=2000, n_intervals=0),
                dbc.Container(
                    [
                        html.H2("LUMINA Admin Cockpit", className="mt-3 mb-3"),
                        dbc.Row(
                            [
                                dbc.Col(
                                    dbc.Card(
                                        dbc.CardBody(
                                            [
                                                html.H5("Parallel realities"),
                                                dcc.Input(
                                                    id="parallel-realities-input",
                                                    type="number",
                                                    min=1,
                                                    max=32,
                                                    value=int(pr_current),
                                                    className="form-control mb-2",
                                                ),
                                                html.Small(
                                                    f"Recommended: {pr_recommended} — {pr_help}",
                                                    className="text-muted d-block mb-2",
                                                ),
                                                dbc.Button(
                                                    "Save",
                                                    id="parallel-realities-save",
                                                    color="primary",
                                                    size="sm",
                                                ),
                                                html.Div(id="parallel-realities-feedback", className="mt-2"),
                                            ]
                                        )
                                    ),
                                    md=4,
                                ),
                                dbc.Col(
                                    dbc.Card(
                                        dbc.CardBody(
                                            [
                                                html.H5("Bot stress options"),
                                                dcc.Checklist(
                                                    id="bot-stress-checks",
                                                    options=[
                                                        {"label": "OHLC DNA stress", "value": "dna"},
                                                        {
                                                            "label": "Neuro OHLC stress rollouts",
                                                            "value": "neuro",
                                                        },
                                                    ],
                                                    value=list(stress_check_val or []),
                                                    className="mb-2",
                                                ),
                                                dbc.Button(
                                                    "Save stress",
                                                    id="bot-stress-save",
                                                    color="secondary",
                                                    size="sm",
                                                ),
                                                html.Div(id="bot-stress-feedback", className="mt-2"),
                                            ]
                                        )
                                    ),
                                    md=4,
                                ),
                                dbc.Col(
                                    dbc.Card(
                                        dbc.CardBody(
                                            [
                                                html.H5("Meters"),
                                                html.Div(id="cost-meter", className="mb-1"),
                                                html.Div(id="pnl-meter", className="mb-1"),
                                                html.Div(id="percentage-meter", className="mb-1"),
                                                html.Div(id="cache-meter", className="mb-1"),
                                                html.Div(id="inference-provider-meter", className="mb-1"),
                                                html.Div(id="inference-latency-meter", className="mb-1"),
                                                html.Div(id="inference-fail-meter", className="mb-1"),
                                            ]
                                        )
                                    ),
                                    md=4,
                                ),
                            ],
                            className="mb-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(dcc.Graph(id="live-chart", figure=empty_fig), md=6),
                                dbc.Col(dcc.Graph(id="equity-curve", figure=empty_fig), md=6),
                            ],
                            className="mb-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(html.Div(id="status-panel"), md=4),
                                dbc.Col(html.Div(id="trade-table"), md=4),
                                dbc.Col(dcc.Graph(id="heatmap", figure=empty_fig), md=4),
                            ],
                            className="mb-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    dcc.Graph(id="inference-provider-figure", figure=empty_fig),
                                    md=4,
                                ),
                                dbc.Col(dcc.Graph(id="swarm-correlation", figure=empty_fig), md=4),
                                dbc.Col(dcc.Graph(id="swarm-allocation", figure=empty_fig), md=4),
                            ],
                            className="mb-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(html.Div(id="swarm-regime-panel"), md=4),
                                dbc.Col(html.Div(id="mode-parity-panel"), md=4),
                                dbc.Col(html.Div(id="blackboard-health-panel"), md=4),
                            ],
                            className="mb-3",
                        ),
                        dbc.Row(
                            [
                                dbc.Col(
                                    dcc.Graph(id="blackboard-health-trend", figure=empty_fig),
                                    md=4,
                                ),
                                dbc.Col(
                                    dcc.Graph(id="drawdown-distribution", figure=empty_fig),
                                    md=4,
                                ),
                                dbc.Col(
                                    dcc.Graph(id="swarm-spread-drilldown", figure=empty_fig),
                                    md=4,
                                ),
                            ],
                            className="mb-3",
                        ),
                        html.Div(id="swarm-spread-detail", className="mb-3"),
                        dbc.Button("Shutdown", id="shutdown-btn", color="danger", className="mb-2"),
                        html.Div(id="shutdown-feedback"),
                        dbc.Modal(
                            [
                                dbc.ModalHeader("Confirm shutdown"),
                                dbc.ModalBody("Stop the admin dashboard process?"),
                                dbc.ModalFooter(
                                    [
                                        dbc.Button("Cancel", id="shutdown-cancel-btn", className="me-2"),
                                        dbc.Button(
                                            "Confirm",
                                            id="shutdown-confirm-btn",
                                            color="danger",
                                        ),
                                    ]
                                ),
                            ],
                            id="shutdown-modal",
                            is_open=False,
                        ),
                    ],
                    fluid=True,
                ),
            ],
            style={"backgroundColor": "#111", "minHeight": "100vh", "color": "#eee"},
        )


__all__ = ["AdminDashboardLayoutBuildMixin"]
