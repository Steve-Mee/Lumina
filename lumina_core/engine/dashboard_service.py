from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import dash
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import plotly.graph_objects as go
import threading
import time
import webbrowser
from dash import Input, Output, dcc, html

from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class DashboardService:
    """Dashboard and performance analytics service backed by engine state."""

    engine: LuminaEngine
    visualization_service: Any | None = None

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("DashboardService requires a LuminaEngine")

    def update_performance_log(self, trade_data: dict[str, Any]) -> None:
        self.engine.update_performance_log(trade_data)

    def generate_strategy_heatmap(self):
        performance_log = self.engine.performance_log
        if len(performance_log) < 20:
            return None

        df_perf = pd.DataFrame(performance_log)
        pivot = (
            df_perf.groupby(["chosen_strategy", "regime"])["pnl"]
            .agg(["mean", "count", lambda x: (x > 0).mean()])
            .reset_index()
        )
        pivot.columns = ["strategy", "regime", "avg_pnl", "trades", "winrate"]

        strategies = pivot["strategy"].unique()
        regimes = pivot["regime"].unique()
        z = np.zeros((len(strategies), len(regimes)))
        for i, strat in enumerate(strategies):
            for j, reg in enumerate(regimes):
                row = pivot[(pivot["strategy"] == strat) & (pivot["regime"] == reg)]
                z[i, j] = row["winrate"].iloc[0] if not row.empty else 0.5

        fig = ff.create_annotated_heatmap(
            z,
            x=list(regimes),
            y=list(strategies),
            annotation_text=np.round(z, 2),
            colorscale="RdYlGn",
            showscale=True,
        )
        fig.update_layout(title="Strategy Heatmap – Winrate per Regime", template="plotly_dark")
        return fig

    def generate_performance_summary(self) -> dict[str, Any]:
        performance_log = self.engine.performance_log
        if not performance_log:
            return {"sharpe": 0, "winrate": 0, "trades": 0}

        pnls = [t.get("pnl", 0) for t in performance_log if t.get("pnl", 0) != 0]
        if not pnls:
            return {"sharpe": 0, "winrate": 0, "trades": 0}

        sharpe = (float(np.mean(pnls)) / (float(np.std(pnls)) + 1e-8)) * float(np.sqrt(252))
        winrate = float(np.mean(np.array(pnls) > 0))
        return {
            "sharpe": round(sharpe, 2),
            "winrate": round(winrate, 3),
            "trades": len(pnls),
            "avg_pnl": round(float(np.mean(pnls)), 1),
        }

    @staticmethod
    def _build_empty_figure(title: str, template: str = "plotly_dark") -> go.Figure:
        fig = go.Figure()
        fig.update_layout(title=title, template=template, height=320)
        return fig

    def _build_swarm_figures(self) -> tuple[go.Figure, go.Figure, html.Div]:
        app = self.engine.app
        swarm_manager = getattr(app, "swarm_manager", None) if app is not None else None
        if swarm_manager is None:
            return (
                self._build_empty_figure("Swarm Correlation (30m)"),
                self._build_empty_figure("Swarm Risk Allocation (%)"),
                html.Div([html.P("Swarm manager not active.")], style={"color": "#bbbbbb"}),
            )

        snapshot = swarm_manager.last_snapshot if hasattr(swarm_manager, "last_snapshot") else {}
        if not snapshot:
            return (
                self._build_empty_figure("Swarm Correlation (30m)"),
                self._build_empty_figure("Swarm Risk Allocation (%)"),
                html.Div([html.P("Swarm snapshot pending...")], style={"color": "#bbbbbb"}),
            )

        matrix_dict = snapshot.get("correlation_matrix", {})
        symbols = list(snapshot.get("symbols", []))
        corr_fig = go.Figure()
        if matrix_dict and symbols:
            z_values = []
            for row_symbol in symbols:
                row_data = matrix_dict.get(row_symbol, {})
                z_values.append([float(row_data.get(col_symbol, 0.0)) for col_symbol in symbols])

            corr_fig = go.Figure(
                data=go.Heatmap(
                    z=z_values,
                    x=symbols,
                    y=symbols,
                    colorscale="RdBu",
                    zmid=0,
                    zmin=-1,
                    zmax=1,
                    colorbar={"title": "Corr"},
                )
            )
            corr_fig.update_layout(title="Swarm Correlation (30m)", template="plotly_dark", height=340)
        else:
            corr_fig = self._build_empty_figure("Swarm Correlation (30m)")

        allocation = snapshot.get("capital_allocation_pct", {})
        alloc_symbols = list(allocation.keys())
        alloc_values = [float(allocation[s]) for s in alloc_symbols]
        alloc_fig = go.Figure()
        if alloc_symbols:
            alloc_fig.add_trace(
                go.Bar(
                    x=alloc_symbols,
                    y=alloc_values,
                    marker_color="#00d4ff",
                    text=[f"{v:.2f}%" for v in alloc_values],
                    textposition="auto",
                )
            )
            alloc_fig.update_layout(
                title="Swarm Risk Allocation (%)",
                yaxis_title="Risk %",
                template="plotly_dark",
                height=340,
            )
        else:
            alloc_fig = self._build_empty_figure("Swarm Risk Allocation (%)")

        regimes = snapshot.get("regimes", {})
        regime_items = [html.Li(f"{sym}: {reg}") for sym, reg in regimes.items()]
        consensus = float(snapshot.get("regime_consensus_multiplier", 1.0) or 1.0)
        arbitrage_signals = snapshot.get("arbitrage_signals", [])
        arb_text = "No active spread signal"
        if arbitrage_signals:
            top = arbitrage_signals[0]
            arb_text = (
                f"{top.get('pair', '')}: {top.get('trade_a', 'HOLD')}/{top.get('trade_b', 'HOLD')} "
                f"(z={float(top.get('zscore', 0.0)):.2f})"
            )

        regime_panel = html.Div(
            [
                html.P(f"Consensus Multiplier: {consensus:.2f}x", style={"color": "#00ff88", "fontWeight": "700"}),
                html.P(f"Primary Symbol: {snapshot.get('primary_symbol', 'N/A')}", style={"color": "#7fd4ff"}),
                html.P(f"Arbitrage: {arb_text}", style={"color": "#ffc857"}),
                html.P("Regime Votes:", style={"color": "#bbbbbb", "marginBottom": "4px"}),
                html.Ul(regime_items if regime_items else [html.Li("No regime votes yet")], style={"marginBottom": 0}),
            ],
            style={"fontSize": "14px"},
        )

        return corr_fig, alloc_fig, regime_panel

    def _build_swarm_spread_drilldown(self, click_data: dict[str, Any] | None) -> tuple[go.Figure, html.Div]:
        app = self.engine.app
        swarm_manager = getattr(app, "swarm_manager", None) if app is not None else None
        if swarm_manager is None or not hasattr(swarm_manager, "nodes"):
            return (
                self._build_empty_figure("Spread Drill-down (click correlation cell)"),
                html.Div("Swarm manager not active.", style={"color": "#bbbbbb"}),
            )

        symbols = list(getattr(swarm_manager, "symbols", []))
        if len(symbols) < 2:
            return (
                self._build_empty_figure("Spread Drill-down (click correlation cell)"),
                html.Div("Need at least 2 symbols for spread drill-down.", style={"color": "#bbbbbb"}),
            )

        symbol_x = symbols[0]
        symbol_y = symbols[1]
        if click_data and isinstance(click_data, dict):
            points = click_data.get("points") or []
            if points:
                point = points[0]
                x_val = str(point.get("x", symbol_x)).strip().upper()
                y_val = str(point.get("y", symbol_y)).strip().upper()
                if x_val in swarm_manager.nodes and y_val in swarm_manager.nodes and x_val != y_val:
                    symbol_x = x_val
                    symbol_y = y_val

        prices_x = list(swarm_manager.nodes[symbol_x].prices_rolling)
        prices_y = list(swarm_manager.nodes[symbol_y].prices_rolling)
        usable = min(len(prices_x), len(prices_y))
        if usable < 12:
            return (
                self._build_empty_figure(f"Spread Drill-down: {symbol_x} vs {symbol_y}"),
                html.Div("Not enough rolling data yet (need ~12 points).", style={"color": "#bbbbbb"}),
            )

        spread = np.array([prices_x[-usable + i] - prices_y[-usable + i] for i in range(usable)], dtype=float)
        spread_mean = float(np.mean(spread))
        spread_std = float(np.std(spread))
        zscore = (spread - spread_mean) / (spread_std + 1e-9)

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=list(range(usable)),
                y=spread.tolist(),
                mode="lines",
                name="Spread",
                line={"color": "#00d4ff", "width": 2},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=list(range(usable)),
                y=zscore.tolist(),
                mode="lines",
                name="Z-score",
                yaxis="y2",
                line={"color": "#ff9f1c", "width": 2},
            )
        )
        fig.add_hline(y=spread_mean, line_dash="dash", line_color="#5f6c7b", annotation_text="Spread mean")
        fig.add_hline(y=2.0, yref="y2", line_dash="dot", line_color="#ff4444", annotation_text="Z +2")
        fig.add_hline(y=-2.0, yref="y2", line_dash="dot", line_color="#00ff88", annotation_text="Z -2")
        fig.update_layout(
            title=f"Spread & Z-score: {symbol_x} - {symbol_y}",
            template="plotly_dark",
            height=340,
            xaxis={"title": "Rolling Index"},
            yaxis={"title": "Spread"},
            yaxis2={"title": "Z-score", "overlaying": "y", "side": "right", "range": [-4, 4]},
            legend={"orientation": "h", "y": 1.12},
        )

        latest_z = float(zscore[-1])
        if latest_z > 2.0:
            signal = "SELL first / BUY second"
        elif latest_z < -2.0:
            signal = "BUY first / SELL second"
        else:
            signal = "No extreme deviation"

        details = html.Div(
            [
                html.P(f"Pair: {symbol_x} vs {symbol_y}", style={"color": "#7fd4ff", "fontWeight": "700"}),
                html.P(f"Latest spread: {spread[-1]:.3f}"),
                html.P(f"Latest z-score: {latest_z:.2f}"),
                html.P(f"Mean-reversion hint: {signal}", style={"color": "#ffc857"}),
            ],
            style={"fontSize": "14px"},
        )
        return fig, details

    @staticmethod
    def _build_inference_status_lines(tracker: dict[str, Any]) -> list[str]:
        requests = int(tracker.get("local_inference_requests", 0))
        total_latency = float(tracker.get("local_inference_latency_ms_total", 0.0))
        avg_latency = total_latency / requests if requests > 0 else 0.0
        active_provider = str(tracker.get("local_inference_last_provider") or "pending")
        failures = int(tracker.get("local_inference_failures", 0))
        local_cost = float(tracker.get("local_inference_cost_today", 0.0))
        lines = [
            (
                f"Inference: {active_provider} | avg {avg_latency:.1f} ms | "
                f"last {float(tracker.get('local_inference_last_latency_ms', 0.0)):.1f} ms"
            ),
            f"Inference Requests: {requests} | Failures: {failures} | Local Cost: ${local_cost:.4f}",
        ]
        warning = str(tracker.get("local_inference_warning", "")).strip()
        if warning:
            lines.append(f"Warning: {warning}")
        return lines

    @staticmethod
    def _build_inference_provider_figure(tracker: dict[str, Any]) -> go.Figure:
        stats = tracker.get("local_inference_provider_stats", {})
        if not isinstance(stats, dict) or not stats:
            return DashboardService._build_empty_figure("Inference Provider History")

        providers = list(stats.keys())
        successes = [int((stats.get(name) or {}).get("successes", 0)) for name in providers]
        failures = [int((stats.get(name) or {}).get("failures", 0)) for name in providers]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="Success", x=providers, y=successes, marker_color="#00ff88"))
        fig.add_trace(go.Bar(name="Failure", x=providers, y=failures, marker_color="#ff6b6b"))
        fig.update_layout(
            title="Inference Provider History",
            template="plotly_dark",
            barmode="stack",
            height=300,
            legend={"orientation": "h", "y": 1.1},
        )
        return fig

    @staticmethod
    def _sum_metric(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float:
        total = 0.0
        expected = {str(k): str(v) for k, v in (labels or {}).items()}
        for payload in snapshot.values():
            if not isinstance(payload, dict):
                continue
            if str(payload.get("name", "")) != metric_name:
                continue
            observed = {str(k): str(v) for k, v in dict(payload.get("labels", {}) or {}).items()}
            if any(observed.get(key) != value for key, value in expected.items()):
                continue
            total += float(payload.get("value", 0.0) or 0.0)
        return total

    def _build_mode_parity_panel(self) -> html.Div:
        mode = str(getattr(self.engine.config, "trade_mode", "paper") or "paper").strip().lower()
        obs = getattr(self.engine, "observability_service", None)
        snapshot = obs.snapshot() if (obs is not None and hasattr(obs, "snapshot")) else {}

        guard_blocks = self._sum_metric(
            snapshot,
            "lumina_mode_guard_block_total",
            labels={"mode": mode},
        )
        reconciled_trades = max(0, len(getattr(self.engine, "trade_log", []) or []))
        reject_denom = guard_blocks + float(reconciled_trades)
        reject_ratio = (guard_blocks / reject_denom) if reject_denom > 0 else 0.0

        parity_delta = self._sum_metric(
            snapshot,
            "lumina_mode_parity_drift_total",
            labels={"baseline": "real", "candidate": "sim_real_guard"},
        )
        eod_force_close_count = self._sum_metric(
            snapshot,
            "lumina_mode_eod_force_close_total",
            labels={"mode": mode},
        )

        reconciler_status = dict(getattr(self.engine, "trade_reconciler_status", {}) or {})
        pending_reconciles = len(getattr(self.engine, "pending_trade_reconciliations", []) or [])
        last_reconciled_trade = reconciler_status.get("last_reconciled_trade", {}) if isinstance(reconciler_status, dict) else {}
        last_reconcile_status = str(last_reconciled_trade.get("status", "n/a")) if isinstance(last_reconciled_trade, dict) else "n/a"

        return html.Div(
            [
                html.P(f"Gate reject ratio: {reject_ratio * 100:.1f}% ({int(guard_blocks)} rejects / {int(reject_denom)} checks)", style={"marginBottom": "6px"}),
                html.P(f"Reconciliation delta (vs real baseline): {parity_delta:.3f}", style={"marginBottom": "6px"}),
                html.P(f"Force-close count ({mode.upper()}): {int(eod_force_close_count)}", style={"marginBottom": "6px"}),
                html.P(f"Reconciler pending: {pending_reconciles} | last status: {last_reconcile_status}", style={"color": "#9fb3c8", "marginBottom": 0}),
            ],
            style={"fontSize": "15px", "color": "#ddd"},
        )

    def start_dashboard(self) -> None:
        app = self.engine.app
        if app is None:
            raise RuntimeError("LuminaEngine is not bound to runtime app")
        if not bool(getattr(app, "DASHBOARD_ENABLED", self.engine.config.dashboard_enabled)):
            return

        dash_app = dash.Dash(__name__, external_stylesheets=[dbc.themes.DARKLY])
        dash_app.layout = dbc.Container(
            [
                html.H1(
                    "LUMINA v45 - Live Human Trading Partner",
                    style={"textAlign": "center", "color": "#00ff88", "marginBottom": "20px"},
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
                        dbc.Col([dbc.Card([dbc.CardBody([html.H5("API Kosten Vandaag", className="text-muted text-center"), html.H2(id="cost-meter", className="text-center", style={"fontSize": "42px", "fontWeight": "bold"})])], color="dark", outline=True)], width=3),
                        dbc.Col([dbc.Card([dbc.CardBody([html.H5("Netto Resultaat Vandaag", className="text-muted text-center"), html.H2(id="pnl-meter", className="text-center", style={"fontSize": "42px", "fontWeight": "bold"})])], color="dark", outline=True)], width=3),
                        dbc.Col([dbc.Card([dbc.CardBody([html.H5("Kosten als % van Resultaat", className="text-muted text-center"), html.H2(id="percentage-meter", className="text-center", style={"fontSize": "42px", "fontWeight": "bold"})])], color="dark", outline=True)], width=3),
                        dbc.Col([dbc.Card([dbc.CardBody([html.H5("Cache Hits Vandaag", className="text-muted text-center"), html.H2(id="cache-meter", className="text-center", style={"fontSize": "42px", "fontWeight": "bold"})])], color="dark", outline=True)], width=3),
                    ],
                    className="mb-4",
                ),
                dbc.Row(
                    [
                        dbc.Col([dbc.Card([dbc.CardBody([html.H5("Inference Provider", className="text-muted text-center"), html.H2(id="inference-provider-meter", className="text-center", style={"fontSize": "34px", "fontWeight": "bold"})])], color="dark", outline=True)], width=4),
                        dbc.Col([dbc.Card([dbc.CardBody([html.H5("Inference Avg Latency", className="text-muted text-center"), html.H2(id="inference-latency-meter", className="text-center", style={"fontSize": "34px", "fontWeight": "bold"})])], color="dark", outline=True)], width=4),
                        dbc.Col([dbc.Card([dbc.CardBody([html.H5("Inference Failures", className="text-muted text-center"), html.H2(id="inference-fail-meter", className="text-center", style={"fontSize": "34px", "fontWeight": "bold"})])], color="dark", outline=True)], width=4),
                    ],
                    className="mb-4",
                ),
                dbc.Row([
                    dbc.Col([dcc.Graph(id="live-chart")], width=8),
                    dbc.Col([html.H5("Account Status & Equity Curve"), html.Div(id="status-panel", style={"fontSize": "18px", "color": "#0ff"}), dcc.Graph(id="equity-curve")], width=4),
                ]),
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
                        dbc.Col([html.H5("Regime Consensus"), html.Div(id="swarm-regime-panel", style={"fontSize": "15px", "color": "#ddd"})], width=2),
                    ],
                    className="mb-3",
                ),
                dbc.Row(
                    [
                        dbc.Col([html.H5("Pair Spread Drill-down"), dcc.Graph(id="swarm-spread-drilldown")], width=9),
                        dbc.Col([html.H5("Pair Detail"), html.Div(id="swarm-spread-detail", style={"fontSize": "15px", "color": "#ddd"})], width=3),
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
                            width=12,
                        ),
                    ],
                    className="mb-3",
                ),
                html.H5("Strategy Heatmap - Winrate per Regime"),
                dcc.Graph(id="heatmap"),
                html.H5("Laatste Trades & Reflections"),
                dbc.Table(id="trade-table", bordered=True, color="dark"),
                dbc.Modal([
                    dbc.ModalHeader("Afsluiten bevestigen"),
                    dbc.ModalBody("Weet je zeker dat je LUMINA volledig wilt afsluiten?"),
                    dbc.ModalFooter([
                        dbc.Button("Annuleren", id="shutdown-cancel-btn", className="ms-auto", n_clicks=0),
                        dbc.Button("Afsluiten", id="shutdown-confirm-btn", color="danger", n_clicks=0),
                    ]),
                ], id="shutdown-modal", centered=True, is_open=False),
                dcc.Interval(id="interval", interval=8000, n_intervals=0),
            ],
            fluid=True,
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
            ],
            Input("interval", "n_intervals"),
        )
        def update_dashboard(_: int):
            chart_base64 = None
            now_ts = time.time()
            if self.visualization_service is not None and now_ts - self.engine.dashboard_last_chart_ts >= int(self.engine.config.dashboard_chart_refresh_sec):
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
            rows = [html.Tr([html.Td(t.get("ts", "")), html.Td(t.get("signal", "")), html.Td(f"${t.get('pnl', 0):,.0f}"), html.Td(f"{t.get('confluence', 0):.2f}")]) for t in self.engine.trade_log[-10:]]
            table_body = [html.Tbody(rows)]

            heatmap_fig = self.generate_strategy_heatmap() or go.Figure()
            tracker = self.engine.cost_tracker
            cost_today = float(tracker.get("today", 0.0))
            pnl_today = self.engine.realized_pnl_today + self.engine.open_pnl
            inference_lines = self._build_inference_status_lines(tracker)

            status = html.Div([
                html.P(f"Mode: {trade_mode} | Equity: ${self.engine.account_equity:,.0f}"),
                html.P(f"Open PnL: ${self.engine.open_pnl:,.0f} | Realized PnL: ${self.engine.realized_pnl_today:,.0f}"),
                html.P(f"Current Dream: {dream_snapshot.get('chosen_strategy')} -> {dream_snapshot.get('signal')} (conf {dream_snapshot.get('confluence_score', 0):.2f})"),
                html.P(inference_lines[0], style={"color": "#7fd4ff"}),
                html.P(inference_lines[1], style={"color": "#bbbbbb"}),
                html.P(inference_lines[2], style={"color": "#ffc857"}) if len(inference_lines) > 2 else html.Div(),
            ])

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
            inference_latency_color = "#00ff88" if inference_avg_latency < 900 else "#ffc857" if inference_avg_latency < 2500 else "#ff4444"
            inference_failure_color = "#00ff88" if inference_failures == 0 else "#ff4444"
            inference_history_fig = self._build_inference_provider_figure(tracker)
            swarm_corr_fig, swarm_alloc_fig, swarm_regime_panel = self._build_swarm_figures()
            mode_parity_panel = self._build_mode_parity_panel()

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
        def update_spread_drilldown(click_data: dict[str, Any] | None, _: int):
            return self._build_swarm_spread_drilldown(click_data)

        @dash_app.callback(Output("shutdown-modal", "is_open"), Input("shutdown-btn", "n_clicks"), Input("shutdown-cancel-btn", "n_clicks"), Input("shutdown-confirm-btn", "n_clicks"), prevent_initial_call=True)
        def toggle_shutdown_modal(open_clicks: int, cancel_clicks: int, confirm_clicks: int):
            if cancel_clicks > 0 or (open_clicks == 0 and confirm_clicks == 0):
                return False
            if open_clicks > 0:
                return True
            return False

        @dash_app.callback(Output("shutdown-feedback", "children"), Input("shutdown-confirm-btn", "n_clicks"), prevent_initial_call=True)
        def execute_shutdown(confirm_clicks: int):
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
            dash_app.run_server(debug=False, port=8050, use_reloader=False)
