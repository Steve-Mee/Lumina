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


class StateVisualizer:
    def __init__(self, engine: Any, metrics: _VisualizerMetrics) -> None:
        self.engine = engine
        self.metrics = metrics

    @property
    def blackboard_health_history(self) -> Any:
        return self.metrics.blackboard_health_history

    @staticmethod
    def _sum_metric(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float:
        return float(StateVisualizer._metrics_sum(snapshot, metric_name, labels=labels))

    @staticmethod
    def _metrics_sum(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float:
        from .metrics_collector import MetricsCollector

        return MetricsCollector.sum_metric(snapshot, metric_name, labels=labels)

    def _collect_blackboard_health_state(self) -> dict[str, Any]:
        return self.metrics.collect_blackboard_health_state()

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
            return StateVisualizer._build_empty_figure("Inference Provider History")

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
        last_reconciled_trade = (
            reconciler_status.get("last_reconciled_trade", {}) if isinstance(reconciler_status, dict) else {}
        )
        last_reconcile_status = (
            str(last_reconciled_trade.get("status", "n/a")) if isinstance(last_reconciled_trade, dict) else "n/a"
        )

        return html.Div(
            [
                html.P(
                    f"Gate reject ratio: {reject_ratio * 100:.1f}% ({int(guard_blocks)} rejects / {int(reject_denom)} checks)",
                    style={"marginBottom": "6px"},
                ),
                html.P(f"Reconciliation delta (vs real baseline): {parity_delta:.3f}", style={"marginBottom": "6px"}),
                html.P(
                    f"Force-close count ({mode.upper()}): {int(eod_force_close_count)}", style={"marginBottom": "6px"}
                ),
                html.P(
                    f"Reconciler pending: {pending_reconciles} | last status: {last_reconcile_status}",
                    style={"color": "#9fb3c8", "marginBottom": 0},
                ),
            ],
            style={"fontSize": "15px", "color": "#ddd"},
        )

    def _build_blackboard_health_trend_figure(self) -> go.Figure:
        fig = self._build_empty_figure("Blackboard Health Trend")
        if not self.blackboard_health_history:
            fig.add_annotation(text="Waiting for blackboard samples...", showarrow=False, font={"color": "#9fb3c8"})
            return fig

        labels = [str(sample.get("ts", "")) for sample in self.blackboard_health_history]
        latency = [float(sample.get("publish_latency", 0.0) or 0.0) for sample in self.blackboard_health_history]
        rejects = [float(sample.get("reject_total", 0.0) or 0.0) for sample in self.blackboard_health_history]
        drops = [float(sample.get("drop_total", 0.0) or 0.0) for sample in self.blackboard_health_history]
        sub_errors = [float(sample.get("sub_error_total", 0.0) or 0.0) for sample in self.blackboard_health_history]
        status_colors = [
            str(sample.get("status_color", "#ffc857") or "#ffc857") for sample in self.blackboard_health_history
        ]

        fig = go.Figure()
        # Left yaxis: latency trend
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=latency,
                mode="lines+markers",
                name="Latency ms",
                line={"color": "#00d4ff", "width": 2},
                marker={"color": status_colors, "size": 8},
            )
        )
        # Right yaxis: counter trends with status coloring
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=rejects,
                mode="lines+markers",
                name="Rejects",
                yaxis="y2",
                line={"color": "#ff6b6b", "width": 2},
                marker={"color": status_colors, "size": 8},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=drops,
                mode="lines+markers",
                name="Drops",
                yaxis="y2",
                line={"color": "#ffc857", "width": 2},
                marker={"color": status_colors, "size": 8},
            )
        )
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=sub_errors,
                mode="lines+markers",
                name="Subscriber Errors",
                yaxis="y2",
                line={"color": "#d946ef", "width": 2},
                marker={"color": status_colors, "size": 8},
            )
        )
        fig.update_layout(
            title="Blackboard Health Trend",
            template="plotly_dark",
            height=280,
            margin={"l": 40, "r": 40, "t": 40, "b": 40},
            xaxis={"title": "Sample"},
            yaxis={"title": "Latency (ms)"},
            yaxis2={"title": "Counters", "overlaying": "y", "side": "right", "rangemode": "tozero"},
            legend={"orientation": "h", "y": 1.15},
        )
        return fig

    def _build_blackboard_health_panel(self, health: dict[str, Any] | None = None) -> html.Div:
        health_data = health or self._collect_blackboard_health_state()
        blackboard_enabled = bool(health_data.get("blackboard_enabled", False))
        meta_enabled = bool(health_data.get("meta_enabled", False))
        status = str(health_data.get("status", "AMBER") or "AMBER")
        status_color = str(health_data.get("status_color", "#ffc857") or "#ffc857")
        publish_latency = float(health_data.get("publish_latency", 0.0) or 0.0)
        reject_total = float(health_data.get("reject_total", 0.0) or 0.0)
        drop_total = float(health_data.get("drop_total", 0.0) or 0.0)
        sub_error_total = float(health_data.get("sub_error_total", 0.0) or 0.0)
        latest_seq = int(health_data.get("latest_seq", 0) or 0)
        latest_conf = float(health_data.get("latest_conf", 0.0) or 0.0)
        reason = str(health_data.get("reason", "") or "")

        return html.Div(
            [
                html.P(
                    f"Status: {status} | Blackboard: {'enabled' if blackboard_enabled else 'disabled'} | Meta-Orchestrator: {'enabled' if meta_enabled else 'disabled'}",
                    style={"marginBottom": "6px", "color": status_color, "fontWeight": "700"},
                ),
                html.P(
                    f"Publish latency sum: {publish_latency:.2f} ms | Rejects: {int(reject_total)} | Drops: {int(drop_total)}",
                    style={"marginBottom": "6px"},
                ),
                html.P(
                    f"Subscriber errors: {int(sub_error_total)} | Latest execution seq: {latest_seq} | Latest conf: {latest_conf:.2f}",
                    style={"marginBottom": "6px", "color": "#9fb3c8"},
                ),
                html.P(f"Reason: {reason}", style={"marginBottom": 0, "color": status_color}),
            ],
            style={"fontSize": "15px", "color": "#ddd"},
        )

    def _build_drawdown_distribution_figure(self) -> go.Figure:
        fig = self._build_empty_figure("Projected Max Drawdown Distribution")
        risk_controller = getattr(self.engine, "risk_controller", None)
        if risk_controller is None:
            fig.add_annotation(text="Risk controller unavailable", showarrow=False, font={"color": "#9fb3c8"})
            return fig

        mc = (
            risk_controller.get_status().get("monte_carlo_drawdown", {})
            if hasattr(risk_controller, "get_status")
            else {}
        )
        if not isinstance(mc, dict):
            mc = {}
        p50 = float(mc.get("p50_pct", 0.0) or 0.0)
        p95 = float(mc.get("p95_pct", 0.0) or 0.0)
        p99 = float(mc.get("p99_pct", 0.0) or 0.0)
        projected = float(mc.get("projected_max_pct", 0.0) or 0.0)
        threshold = float(mc.get("threshold_pct", 0.0) or 0.0)

        if projected <= 0.0 and p95 <= 0.0:
            fig.add_annotation(text="Waiting for Monte-Carlo samples...", showarrow=False, font={"color": "#9fb3c8"})
            return fig

        labels = ["P50", "P95", "P99", "Projected Max"]
        values = [p50, p95, p99, projected]
        colors = ["#00d4ff", "#00ff88", "#ffc857", "#ff6b6b" if projected > threshold > 0 else "#9fb3c8"]
        fig = go.Figure(
            data=[
                go.Bar(x=labels, y=values, marker_color=colors, text=[f"{v:.2f}%" for v in values], textposition="auto")
            ]
        )
        if threshold > 0.0:
            fig.add_hline(
                y=threshold, line_dash="dash", line_color="#ff4444", annotation_text=f"Threshold {threshold:.2f}%"
            )
        fig.update_layout(
            title="Projected Max Drawdown Distribution",
            yaxis_title="Drawdown %",
            template="plotly_dark",
            height=300,
        )
        return fig

    @staticmethod
    def build_empty_figure(title: str, template: str = "plotly_dark") -> go.Figure:
        return StateVisualizer._build_empty_figure(title, template)

    def build_swarm_figures(self) -> tuple[go.Figure, go.Figure, html.Div]:
        return self._build_swarm_figures()

    def build_swarm_spread_drilldown(self, click_data: dict[str, Any] | None) -> tuple[go.Figure, html.Div]:
        return self._build_swarm_spread_drilldown(click_data)

    @staticmethod
    def build_inference_status_lines(tracker: dict[str, Any]) -> list[str]:
        return StateVisualizer._build_inference_status_lines(tracker)

    @staticmethod
    def build_inference_provider_figure(tracker: dict[str, Any]) -> go.Figure:
        return StateVisualizer._build_inference_provider_figure(tracker)

    def build_mode_parity_panel(self) -> html.Div:
        return self._build_mode_parity_panel()

    def build_blackboard_health_trend_figure(self) -> go.Figure:
        return self._build_blackboard_health_trend_figure()

    def build_blackboard_health_panel(self, health: dict[str, Any] | None = None) -> html.Div:
        return self._build_blackboard_health_panel(health)

    def build_drawdown_distribution_figure(self) -> go.Figure:
        return self._build_drawdown_distribution_figure()
