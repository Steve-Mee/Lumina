"""Inference + empty figure builders (M5 extract)."""
from __future__ import annotations

from typing import Any

import plotly.graph_objects as go


class StateVisualizerInferenceMixin:
    @staticmethod
    def _build_empty_figure(title: str, template: str = "plotly_dark") -> go.Figure:
        fig = go.Figure()
        fig.update_layout(title=title, template=template, height=320)
        return fig

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

    @staticmethod
    def build_empty_figure(title: str, template: str = "plotly_dark") -> go.Figure:
        return StateVisualizer._build_empty_figure(title, template)

    @staticmethod
    def build_inference_status_lines(tracker: dict[str, Any]) -> list[str]:
        return StateVisualizer._build_inference_status_lines(tracker)

    @staticmethod
    def build_inference_provider_figure(tracker: dict[str, Any]) -> go.Figure:
        return StateVisualizer._build_inference_provider_figure(tracker)

