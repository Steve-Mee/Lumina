"""Blackboard health + mode parity + drawdown panels (M5 extract)."""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from dash import html


class StateVisualizerHealthMixin:
    @property
    def blackboard_health_history(self) -> Any:
        return self.metrics.blackboard_health_history

    def _collect_blackboard_health_state(self) -> dict[str, Any]:
        return self.metrics.collect_blackboard_health_state()

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

    def build_mode_parity_panel(self) -> html.Div:
        return self._build_mode_parity_panel()

    def build_blackboard_health_trend_figure(self) -> go.Figure:
        return self._build_blackboard_health_trend_figure()

    def build_blackboard_health_panel(self, health: dict[str, Any] | None = None) -> html.Div:
        return self._build_blackboard_health_panel(health)

    def build_drawdown_distribution_figure(self) -> go.Figure:
        return self._build_drawdown_distribution_figure()
