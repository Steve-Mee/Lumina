"""Plot/arbitrage helpers for MultiSymbolSwarmManager (global residual)."""
from __future__ import annotations

import itertools
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

class MultiSymbolSwarmPlotMixin:
    def detect_inter_symbol_arbitrage(self) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        min_zscore = float(getattr(self.engine.config, "swarm_arb_min_zscore", 2.0) or 2.0)
        cost_per_leg = float(getattr(self.engine.config, "swarm_arb_cost_per_leg", 0.15) or 0.15)
        min_net_edge = float(getattr(self.engine.config, "swarm_arb_min_net_edge", 0.05) or 0.05)
        for a, b in itertools.combinations(self.symbols, 2):
            a_prices = list(self.nodes[a].prices_rolling)
            b_prices = list(self.nodes[b].prices_rolling)
            usable = min(len(a_prices), len(b_prices))
            if usable < 10:
                continue

            spreads = [a_prices[-usable + i] - b_prices[-usable + i] for i in range(usable)]
            z = self._zscore(spreads)
            if abs(z) < min_zscore:
                continue

            spread_std = float(np.std(np.array(spreads, dtype=float))) if spreads else 0.0
            gross_edge = abs(float(z)) * spread_std
            total_cost = cost_per_leg * 2.0
            net_edge = gross_edge - total_cost
            if net_edge < min_net_edge:
                continue

            if z > 0:
                signals.append(
                    {
                        "pair": f"{a}-{b}",
                        "zscore": round(float(z), 3),
                        "gross_edge": round(gross_edge, 4),
                        "net_edge": round(net_edge, 4),
                        "estimated_cost": round(total_cost, 4),
                        "trade_a": "SELL",
                        "trade_b": "BUY",
                        "reason": "Spread above mean; expect reversion",
                    }
                )
            else:
                signals.append(
                    {
                        "pair": f"{a}-{b}",
                        "zscore": round(float(z), 3),
                        "gross_edge": round(gross_edge, 4),
                        "net_edge": round(net_edge, 4),
                        "estimated_cost": round(total_cost, 4),
                        "trade_a": "BUY",
                        "trade_b": "SELL",
                        "reason": "Spread below mean; expect reversion",
                    }
                )
        return signals
    def apply_to_primary_dream(self) -> dict[str, Any]:
        if not self.last_snapshot:
            return {}

        allocation = self.last_snapshot.get("capital_allocation_pct", {})
        alloc_pct = float(allocation.get(self.primary_symbol, 0.0) or 0.0)
        max_risk = max(1e-6, float(self.engine.config.max_risk_percent))
        consensus_mult = float(self.last_snapshot.get("regime_consensus_multiplier", 1.0) or 1.0)
        qty_multiplier = max(0.1, (alloc_pct / max_risk) * consensus_mult) if alloc_pct > 0 else 0.1

        updates: dict[str, Any] = {
            "swarm_ts": self.last_snapshot.get("ts"),
            "swarm_primary_symbol": self.primary_symbol,
            "position_size_multiplier": float(qty_multiplier),
            "swarm_consensus_multiplier": float(consensus_mult),
            "swarm_alloc_risk_percent": float(alloc_pct),
            "swarm_arbitrage_signals": self.last_snapshot.get("arbitrage_signals", []),
        }

        if self.last_snapshot.get("arbitrage_signals"):
            first = self.last_snapshot["arbitrage_signals"][0]
            pair = str(first.get("pair", ""))
            if self.primary_symbol in pair:
                if pair.startswith(self.primary_symbol + "-"):
                    updates["swarm_arb_signal"] = str(first.get("trade_a", "HOLD"))
                else:
                    updates["swarm_arb_signal"] = str(first.get("trade_b", "HOLD"))
                updates["swarm_arb_reason"] = str(first.get("reason", "inter-symbol spread signal"))

        blackboard = getattr(self.engine, "blackboard", None)
        if blackboard is not None and hasattr(blackboard, "add_proposal"):
            confidence = float(min(1.0, max(0.0, consensus_mult / max(1.0, float(self.trend_consensus_multiplier)))))
            blackboard.add_proposal(
                topic="agent.swarm.proposal",
                producer="swarm_manager",
                payload=updates,
                confidence=confidence,
            )
        else:
            self.engine.set_current_dream_fields(updates)
        return updates
    def generate_dashboard_plot(self, output_path: str = "journal/swarm_dashboard.html") -> str | None:
        try:
            from plotly import graph_objects as go
        except Exception:
            logging.exception(
                "Unhandled broad exception fallback in lumina_core/engine/multi_symbol_swarm_manager.py:386"
            )
            return None

        fig = go.Figure()

        mes_curve = self.nodes.get("MES JUN26")
        if mes_curve is not None and len(mes_curve.equity_curve) > 1:
            fig.add_trace(
                go.Scatter(
                    y=mes_curve.equity_curve,
                    mode="lines",
                    name="Swarm MES node",
                    line={"width": 2},
                )
            )

        for symbol, node in self.nodes.items():
            if len(node.equity_curve) <= 1:
                continue
            fig.add_trace(
                go.Scatter(
                    y=node.equity_curve,
                    mode="lines",
                    name=f"Swarm {symbol}",
                    line={"width": 1.5},
                    opacity=0.75,
                )
            )

        if len(self.engine.equity_curve) > 1:
            fig.add_trace(
                go.Scatter(
                    y=self.engine.equity_curve,
                    mode="lines",
                    name="Single MES baseline",
                    line={"dash": "dash", "width": 2},
                )
            )

        fig.update_layout(
            title="Lumina Swarm Equity Curves vs Single MES",
            xaxis_title="Trade/Event Index",
            yaxis_title="Equity ($)",
            template="plotly_white",
            legend={"orientation": "h", "y": 1.1},
        )

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(out), include_plotlyjs="cdn")
        return str(out)
