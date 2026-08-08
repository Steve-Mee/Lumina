"""Swarm dashboard figures (M5 extract)."""
from __future__ import annotations

from typing import Any

import numpy as np
import plotly.graph_objects as go
from dash import html


class StateVisualizerSwarmMixin:
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

    def build_swarm_figures(self) -> tuple[go.Figure, go.Figure, html.Div]:
        return self._build_swarm_figures()

    def build_swarm_spread_drilldown(self, click_data: dict[str, Any] | None) -> tuple[go.Figure, html.Div]:
        return self._build_swarm_spread_drilldown(click_data)

