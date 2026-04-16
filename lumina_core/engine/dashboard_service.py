from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
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
    blackboard_health_history: deque[dict[str, float | str]] = field(init=False)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("DashboardService requires a LuminaEngine")
        history_points = max(5, int(getattr(self.engine.config, "blackboard_health_trend_points", 30) or 30))
        self.blackboard_health_history = deque(maxlen=history_points)

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
        red_latency = float(getattr(self.engine.config, "blackboard_health_latency_red_ms", 1000.0) or 1000.0)
        amber_latency = float(getattr(self.engine.config, "blackboard_health_latency_amber_ms", 250.0) or 250.0)
        min_confidence = float(getattr(self.engine.config, "blackboard_health_min_confidence", 0.80) or 0.80)
        if not blackboard_enabled:
            return ("RED", "#ff6b6b", "blackboard disabled")
        if reject_total > 0:
            return ("RED", "#ff6b6b", "unauthorized or malformed events rejected")
        if sub_error_total > 0:
            return ("RED", "#ff6b6b", "subscriber errors detected")
        if publish_latency > red_latency:
            return ("RED", "#ff6b6b", f"publish latency above {red_latency:.0f} ms")
        if has_execution_event and latest_conf < min_confidence:
            return ("RED", "#ff6b6b", f"latest aggregate confidence below {min_confidence:.2f}")
        if drop_total > 0:
            return ("AMBER", "#ffc857", "non-critical telemetry drops detected")
        if publish_latency > amber_latency:
            return ("AMBER", "#ffc857", f"publish latency above {amber_latency:.0f} ms")
        if not meta_enabled:
            return ("AMBER", "#ffc857", "meta-orchestrator not enabled")
        if not has_execution_event:
            return ("AMBER", "#ffc857", "no execution aggregate observed yet")
        return ("GREEN", "#00ff88", "blackboard and orchestrator healthy")

    def _collect_blackboard_health_state(self) -> dict[str, Any]:
        obs = getattr(self.engine, "observability_service", None)
        snapshot = obs.snapshot() if (obs is not None and hasattr(obs, "snapshot")) else {}
        publish_latency = self._sum_metric(snapshot, "lumina_blackboard_publish_latency_ms")
        reject_total = self._sum_metric(snapshot, "lumina_blackboard_reject_total")
        drop_total = self._sum_metric(snapshot, "lumina_blackboard_drop_total")
        sub_error_total = self._sum_metric(snapshot, "lumina_blackboard_subscription_error_total")

        blackboard = getattr(self.engine, "blackboard", None)
        meta_agent = getattr(self.engine, "meta_agent_orchestrator", None)
        execution_event = blackboard.latest("execution.aggregate") if (blackboard is not None and hasattr(blackboard, "latest")) else None
        has_execution_event = execution_event is not None
        latest_conf = float(getattr(execution_event, "confidence", 0.0) or 0.0) if execution_event is not None else 0.0
        latest_seq = int(getattr(execution_event, "sequence", 0) or 0) if execution_event is not None else 0
        status, status_color, reason = self._classify_blackboard_health(
            blackboard_enabled=blackboard is not None,
            meta_enabled=meta_agent is not None,
            publish_latency=publish_latency,
            reject_total=reject_total,
            drop_total=drop_total,
            sub_error_total=sub_error_total,
            latest_conf=latest_conf,
            has_execution_event=has_execution_event,
        )
        return {
            "blackboard_enabled": blackboard is not None,
            "meta_enabled": meta_agent is not None,
            "publish_latency": publish_latency,
            "reject_total": reject_total,
            "drop_total": drop_total,
            "sub_error_total": sub_error_total,
            "latest_conf": latest_conf,
            "latest_seq": latest_seq,
            "has_execution_event": has_execution_event,
            "status": status,
            "status_color": status_color,
            "reason": reason,
        }

    def _record_blackboard_health_sample(self, health: dict[str, Any]) -> None:
        self.blackboard_health_history.append(
            {
                "ts": time.strftime("%H:%M:%S"),
                "publish_latency": float(health.get("publish_latency", 0.0) or 0.0),
                "reject_total": float(health.get("reject_total", 0.0) or 0.0),
                "drop_total": float(health.get("drop_total", 0.0) or 0.0),
                "sub_error_total": float(health.get("sub_error_total", 0.0) or 0.0),
                "status": str(health.get("status", "AMBER") or "AMBER"),
                "status_color": str(health.get("status_color", "#ffc857") or "#ffc857"),
            }
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
        status_colors = [str(sample.get("status_color", "#ffc857") or "#ffc857") for sample in self.blackboard_health_history]

        fig = go.Figure()
        # Left yaxis: latency trend
        fig.add_trace(go.Scatter(
            x=labels,
            y=latency,
            mode="lines+markers",
            name="Latency ms",
            line={"color": "#00d4ff", "width": 2},
            marker={"color": status_colors, "size": 8}
        ))
        # Right yaxis: counter trends with status coloring
        fig.add_trace(go.Scatter(
            x=labels,
            y=rejects,
            mode="lines+markers",
            name="Rejects",
            yaxis="y2",
            line={"color": "#ff6b6b", "width": 2},
            marker={"color": status_colors, "size": 8}
        ))
        fig.add_trace(go.Scatter(
            x=labels,
            y=drops,
            mode="lines+markers",
            name="Drops",
            yaxis="y2",
            line={"color": "#ffc857", "width": 2},
            marker={"color": status_colors, "size": 8}
        ))
        fig.add_trace(go.Scatter(
            x=labels,
            y=sub_errors,
            mode="lines+markers",
            name="Subscriber Errors",
            yaxis="y2",
            line={"color": "#d946ef", "width": 2},
            marker={"color": status_colors, "size": 8}
        ))
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
                html.P(f"Status: {status} | Blackboard: {'enabled' if blackboard_enabled else 'disabled'} | Meta-Orchestrator: {'enabled' if meta_enabled else 'disabled'}", style={"marginBottom": "6px", "color": status_color, "fontWeight": "700"}),
                html.P(f"Publish latency sum: {publish_latency:.2f} ms | Rejects: {int(reject_total)} | Drops: {int(drop_total)}", style={"marginBottom": "6px"}),
                html.P(f"Subscriber errors: {int(sub_error_total)} | Latest execution seq: {latest_seq} | Latest conf: {latest_conf:.2f}", style={"marginBottom": "6px", "color": "#9fb3c8"}),
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
            fig.add_hline(y=threshold, line_dash="dash", line_color="#ff4444", annotation_text=f"Threshold {threshold:.2f}%")
        fig.update_layout(
            title="Projected Max Drawdown Distribution",
            yaxis_title="Drawdown %",
            template="plotly_dark",
            height=300,
        )
        return fig

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
                Output("blackboard-health-panel", "children"),
                Output("blackboard-health-trend", "figure"),
                Output("drawdown-distribution", "figure"),
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
