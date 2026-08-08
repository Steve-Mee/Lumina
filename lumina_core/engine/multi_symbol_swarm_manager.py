from __future__ import annotations
import logging

import itertools
import json
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .dream_state import DreamState
from .lumina_engine import LuminaEngine
from .market_data_manager import MarketDataManager
from lumina_core.engine.multi_symbol_swarm_plot import MultiSymbolSwarmPlotMixin


@dataclass(slots=True)
class SymbolNode:
    symbol: str
    market_data: MarketDataManager = field(default_factory=MarketDataManager)
    dream_state: DreamState = field(default_factory=DreamState)
    prices_rolling: deque[float] = field(default_factory=lambda: deque(maxlen=30))
    returns_rolling: deque[float] = field(default_factory=lambda: deque(maxlen=30))
    regimes_rolling: deque[str] = field(default_factory=lambda: deque(maxlen=30))
    pnl_history: deque[float] = field(default_factory=lambda: deque(maxlen=200))
    equity_curve: list[float] = field(default_factory=lambda: [50000.0])
    last_price: float = 0.0


@dataclass(slots=True)
class MultiSymbolSwarmManager(MultiSymbolSwarmPlotMixin):
    """Coordinates multi-symbol state and cross-asset overlays for execution."""

    engine: LuminaEngine
    symbols: list[str]
    rolling_window_minutes: int = 30
    trend_consensus_threshold: int = 3
    trend_consensus_multiplier: float = 1.6

    nodes: dict[str, SymbolNode] = field(init=False, default_factory=dict)
    primary_symbol: str = field(init=False, default="")
    last_snapshot: dict[str, Any] = field(init=False, default_factory=dict)
    last_vector_store_ts: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("MultiSymbolSwarmManager requires a LuminaEngine")

        unique_symbols: list[str] = []
        for raw in self.symbols:
            symbol = str(raw).strip().upper()
            if symbol and symbol not in unique_symbols:
                unique_symbols.append(symbol)
        if not unique_symbols:
            raise ValueError("MultiSymbolSwarmManager requires at least one symbol")

        self.symbols = unique_symbols
        self.primary_symbol = str(self.engine.config.instrument).strip().upper()
        if self.primary_symbol not in self.symbols:
            self.primary_symbol = self.symbols[0]

        maxlen = max(10, int(self.rolling_window_minutes))
        self.nodes = {}
        for symbol in self.symbols:
            node = SymbolNode(symbol=symbol)
            node.prices_rolling = deque(maxlen=maxlen)
            node.returns_rolling = deque(maxlen=maxlen)
            node.regimes_rolling = deque(maxlen=maxlen)
            self.nodes[symbol] = node

    def process_quote_tick(
        self,
        *,
        symbol: str,
        ts: datetime,
        price: float,
        bid: float,
        ask: float,
        volume_cumulative: int,
    ) -> None:
        symbol_key = str(symbol).strip().upper()
        if symbol_key not in self.nodes:
            return

        node = self.nodes[symbol_key]
        node.market_data.process_quote_tick(
            ts=ts,
            price=float(price),
            bid=float(bid),
            ask=float(ask),
            volume_cumulative=int(volume_cumulative),
        )

        last = float(price)
        prev = float(node.last_price) if node.last_price else 0.0
        node.prices_rolling.append(last)
        if prev > 0:
            node.returns_rolling.append((last - prev) / prev)
        node.last_price = last

        ohlc = node.market_data.copy_ohlc()
        if len(ohlc) >= 20:
            try:
                regime = self.engine.detect_market_regime(ohlc)
            except Exception:
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/engine/multi_symbol_swarm_manager.py:108"
                )
                regime = "NEUTRAL"
        else:
            regime = "NEUTRAL"
        node.regimes_rolling.append(str(regime).upper())
        node.dream_state.update({"regime": str(regime).upper(), "last_price": last, "symbol": symbol_key})

    def ingest_historical_rows(self, symbol: str, rows_df: pd.DataFrame) -> None:
        symbol_key = str(symbol).strip().upper()
        if symbol_key not in self.nodes or rows_df is None or rows_df.empty:
            return

        node = self.nodes[symbol_key]
        expected_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        if not expected_cols.issubset(set(rows_df.columns)):
            return

        node.market_data.append_ohlc_rows(rows_df)
        tail = rows_df.tail(self.rolling_window_minutes)
        closes = [float(v) for v in tail["close"].tolist()]
        for px in closes:
            prev = node.prices_rolling[-1] if node.prices_rolling else 0.0
            node.prices_rolling.append(px)
            if prev > 0:
                node.returns_rolling.append((px - prev) / prev)
            node.last_price = px

        if len(node.market_data.ohlc_1min) >= 20:
            try:
                regime = self.engine.detect_market_regime(node.market_data.copy_ohlc())
            except Exception:
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/engine/multi_symbol_swarm_manager.py:138"
                )
                regime = "NEUTRAL"
            node.regimes_rolling.append(str(regime).upper())

    def build_correlation_matrix(self) -> pd.DataFrame:
        min_len = min((len(n.returns_rolling) for n in self.nodes.values()), default=0)
        if min_len < 5:
            return pd.DataFrame(index=self.symbols, columns=self.symbols, dtype=float)

        data = {sym: np.array(list(node.returns_rolling)[-min_len:], dtype=float) for sym, node in self.nodes.items()}
        matrix = pd.DataFrame(data).corr()
        return matrix.reindex(index=self.symbols, columns=self.symbols)

    def _regime_consensus_multiplier(self) -> tuple[float, dict[str, str]]:
        regimes: dict[str, str] = {}
        trending_count = 0
        for symbol, node in self.nodes.items():
            regime = node.regimes_rolling[-1] if node.regimes_rolling else "NEUTRAL"
            regime = str(regime).upper()
            regimes[symbol] = regime
            if regime == "TRENDING":
                trending_count += 1

        if trending_count >= int(self.trend_consensus_threshold):
            return float(self.trend_consensus_multiplier), regimes
        return 1.0, regimes

    @staticmethod
    def _kelly_fraction(pnls: list[float]) -> float:
        if len(pnls) < 12:
            return 0.25

        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        if not wins or not losses:
            return 0.2

        win_rate = len(wins) / max(1, len(pnls))
        avg_win = float(np.mean(wins))
        avg_loss = float(np.mean(losses))
        if avg_loss <= 0:
            return 0.2

        payoff = avg_win / avg_loss
        kelly = win_rate - ((1 - win_rate) / max(1e-6, payoff))
        return float(max(0.05, min(0.5, kelly)))

    def compute_capital_allocation(self, max_risk_percent: float) -> dict[str, float]:
        if max_risk_percent <= 0:
            return {s: 0.0 for s in self.symbols}

        inv_vol: dict[str, float] = {}
        kelly_scaled: dict[str, float] = {}
        for symbol, node in self.nodes.items():
            rets = np.array(list(node.returns_rolling), dtype=float)
            vol = float(np.std(rets)) if len(rets) >= 3 else 0.0
            inv_vol[symbol] = 1.0 / max(1e-6, vol)
            kelly_scaled[symbol] = self._kelly_fraction(list(node.pnl_history))

        raw_weights = {s: inv_vol[s] * kelly_scaled[s] for s in self.symbols}
        weight_sum = float(sum(raw_weights.values()))
        if weight_sum <= 0:
            equal = float(max_risk_percent) / max(1, len(self.symbols))
            return {s: equal for s in self.symbols}

        alloc = {s: (raw_weights[s] / weight_sum) * float(max_risk_percent) for s in self.symbols}

        total = float(sum(alloc.values()))
        if total > max_risk_percent and total > 0:
            scale = float(max_risk_percent) / total
            alloc = {s: v * scale for s, v in alloc.items()}
        return alloc

    @staticmethod
    def _zscore(values: list[float]) -> float:
        if len(values) < 8:
            return 0.0
        arr = np.array(values, dtype=float)
        mu = float(np.mean(arr))
        sd = float(np.std(arr))
        if sd <= 1e-9:
            return 0.0
        return (float(arr[-1]) - mu) / sd


    def run_cycle(self) -> dict[str, Any]:
        corr = self.build_correlation_matrix()
        multiplier, regimes = self._regime_consensus_multiplier()
        allocation = self.compute_capital_allocation(self.engine.config.max_risk_percent)
        arbitrage_signals = self.detect_inter_symbol_arbitrage()

        primary_alloc = allocation.get(self.primary_symbol, 0.0)
        base_risk = max(1e-6, float(self.engine.config.max_risk_percent))
        position_size_multiplier = (primary_alloc / base_risk) * multiplier if primary_alloc > 0 else 0.0

        snapshot = {
            "ts": datetime.now().isoformat(),
            "symbols": list(self.symbols),
            "primary_symbol": self.primary_symbol,
            "regime_consensus_multiplier": float(multiplier),
            "regimes": regimes,
            "capital_allocation_pct": allocation,
            "primary_position_size_multiplier": float(max(0.1, position_size_multiplier)),
            "arbitrage_signals": arbitrage_signals,
            "correlation_matrix": corr.fillna(0.0).round(4).to_dict() if not corr.empty else {},
        }
        self.last_snapshot = snapshot

        now_ts = time.time()
        if now_ts - self.last_vector_store_ts >= 60:
            self._store_cross_symbol_experience(snapshot)
            self.last_vector_store_ts = now_ts

        return snapshot

    def _store_cross_symbol_experience(self, snapshot: dict[str, Any]) -> None:
        if self.engine.app is None:
            return
        store_fn = getattr(self.engine.app, "store_experience_to_vector_db", None)
        if not callable(store_fn):
            return

        try:
            summary = {
                "regime_consensus_multiplier": snapshot.get("regime_consensus_multiplier", 1.0),
                "regimes": snapshot.get("regimes", {}),
                "capital_allocation_pct": snapshot.get("capital_allocation_pct", {}),
                "arbitrage_signals": snapshot.get("arbitrage_signals", []),
            }
            store_fn(
                context=f"Swarm cycle summary: {json.dumps(summary, ensure_ascii=True)}",
                metadata={
                    "type": "cross_symbol_swarm",
                    "date": datetime.now().isoformat(),
                    "symbols": ",".join(self.symbols),
                },
            )
        except Exception:
            logging.exception(
                "Unhandled broad exception fallback in lumina_core/engine/multi_symbol_swarm_manager.py:326"
            )
            return


    def register_trade_result(self, symbol: str, pnl: float) -> None:
        """Append per-symbol realized trade PnL for Kelly-style heuristics.

        In REAL mode the caller should pass **broker-reconciled** realized PnL only
        (same provenance as ``EconomicPnLService``); never RL-only shaped Gym rewards.
        """
        symbol_key = str(symbol).strip().upper()
        if symbol_key not in self.nodes:
            return

        node = self.nodes[symbol_key]
        pnl_val = float(pnl)
        node.pnl_history.append(pnl_val)

        last_equity = float(node.equity_curve[-1]) if node.equity_curve else 50000.0
        node.equity_curve.append(last_equity + pnl_val)

