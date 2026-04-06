# CANONICAL IMPLEMENTATION – v50 Living Organism
from __future__ import annotations

from typing import Any

from .multi_symbol_swarm_manager import MultiSymbolSwarmManager
from .lumina_engine import LuminaEngine


class SwarmManager(MultiSymbolSwarmManager):
    """Compatibility wrapper exposing the requested swarm API on top of the current implementation."""

    def __init__(self, engine: LuminaEngine):
        symbols = [str(s).strip().upper() for s in getattr(engine.config, "swarm_symbols", []) if str(s).strip()]
        if not symbols:
            symbols = [str(getattr(engine.config, "instrument", "MES JUN26")).strip().upper()]
        super().__init__(engine=engine, symbols=symbols)

    def run_swarm_cycle(self) -> dict[str, Any]:
        snapshot = self.run_cycle()
        allocation = snapshot.get("capital_allocation_pct", {}) if isinstance(snapshot, dict) else {}
        correlation_matrix = snapshot.get("correlation_matrix", {}) if isinstance(snapshot, dict) else {}
        regimes = snapshot.get("regimes", {}) if isinstance(snapshot, dict) else {}

        global_regime = "NEUTRAL"
        if isinstance(regimes, dict) and regimes:
            regime_votes: dict[str, int] = {}
            for regime in regimes.values():
                key = str(regime).upper()
                regime_votes[key] = regime_votes.get(key, 0) + 1
            global_regime = max(regime_votes, key=regime_votes.get)
            if float(snapshot.get("regime_consensus_multiplier", 1.0) or 1.0) <= 1.0:
                global_regime = "NEUTRAL"

        correlation_to_primary = {}
        primary_symbol = str(snapshot.get("primary_symbol", ""))
        if isinstance(correlation_matrix, dict) and primary_symbol:
            primary_row = correlation_matrix.get(primary_symbol, {})
            if isinstance(primary_row, dict):
                correlation_to_primary = {
                    str(symbol): float(value)
                    for symbol, value in primary_row.items()
                    if str(symbol) != primary_symbol
                }

        arbitrage_signals = snapshot.get("arbitrage_signals", []) if isinstance(snapshot, dict) else []
        arbitrage = {"signal": "NONE", "zscore": 0.0}
        if isinstance(arbitrage_signals, list) and arbitrage_signals:
            first = arbitrage_signals[0]
            if isinstance(first, dict):
                arbitrage = {
                    "signal": f"{first.get('trade_a', 'HOLD')}_{first.get('pair', 'PAIR')}_{first.get('trade_b', 'HOLD')}",
                    "zscore": float(first.get("zscore", 0.0) or 0.0),
                    "edge": str(first.get("reason", "spread_mean_reversion")),
                }

        return {
            "global_regime": global_regime,
            "allocation": allocation,
            "correlation": correlation_to_primary,
            "arbitrage": arbitrage,
            "snapshot": snapshot,
        }