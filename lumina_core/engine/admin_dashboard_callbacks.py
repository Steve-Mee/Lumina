"""Dash admin dashboard callback registration."""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
import threading
import time
from dash import Input, Output, State, html

from lumina_core.evolution.bot_stress_choices import (
    save_bot_stress_choices,
)
from lumina_core.evolution.parallel_reality_config import (
    save_parallel_realities_session,
)


class AdminDashboardCallbacksMixin:
    """Registers Dash callbacks for the admin dashboard."""

    def _register_admin_dashboard_callbacks(self, dash_app: Any, app: Any) -> None:
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
                print(f"[{time.strftime('%H:%M:%S')}] Shutdown button confirmed from dashboard")
                threading.Thread(target=app.emergency_stop, daemon=False).start()
                return "App wordt afgesloten..."
            return ""

