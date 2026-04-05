from __future__ import annotations

import copy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from lumina_core.runtime_context import RuntimeContext


class RealisticBacktesterEngine:
    """
    Realistische backtester met slippage, commission, partial fills en queue simulation.
    Gebruikt FastPathEngine + LocalInferenceEngine voor eerlijke signalen.
    """

    def __init__(self, context: RuntimeContext):
        self.context = context
        self.logger = context.logger
        self.fast_path = context.fast_path          # uit stap 1.2
        self.local_engine = context.local_engine    # uit LocalInferenceEngine
        self.commission_per_side_pt = 0.25          # MES real commission
        self.slippage_base_ticks = 0.25             # basis
        self.partial_fill_prob = 0.35               # 35% kans op partial

    def _calculate_slippage(self, price: float, volume: float, regime: str, side: str) -> float:
        """0.25-0.5 tick slippage, hoger bij lage volume / volatile regime"""
        regime_mult = {
            "TRENDING": 1.0, "BREAKOUT": 1.3, "VOLATILE": 1.8,
            "RANGING": 0.7, "NEUTRAL": 1.0
        }.get(regime.upper(), 1.0)

        vol_factor = max(0.5, min(2.0, 10000 / (volume + 1)))  # lage volume = meer slippage
        slippage_ticks = self.slippage_base_ticks * regime_mult * vol_factor

        # Random noise voor realisme
        noise = np.random.normal(0, 0.1) * slippage_ticks
        slippage_price = slippage_ticks * 0.25 * (1 if side == "BUY" else -1) + noise * 0.25
        return round(slippage_price, 2)

    def _apply_commission(self, qty: int, side: str) -> float:
        """0.25 point per side per contract"""
        return qty * self.commission_per_side_pt * 5.0  # MES 1 point = $5

    def _simulate_partial_fill(self, qty: int, price: float, volume: float) -> Tuple[int, float]:
        """Partial fill simulatie + queue position"""
        if np.random.rand() > self.partial_fill_prob:
            return qty, price  # full fill

        fill_pct = np.random.uniform(0.3, 0.85)
        filled_qty = int(qty * fill_pct)
        # Rest queued -> gemiddelde prijs iets slechter
        queue_slip = 0.25 * (1 if np.random.rand() > 0.5 else -1)
        fill_price = price + queue_slip
        return filled_qty, round(fill_price, 2)

    def run_backtest_on_snapshot(self, snapshot: pd.DataFrame, days: int = 5) -> Dict[str, Any]:
        """Hoofdmethode - realistische backtest"""
        df = snapshot.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

        equity = 50000.0
        position = 0
        entry_price = 0.0
        pnl_history = []
        trades = []
        equity_curve = [equity]

        for i in range(60, len(df)):
            row = df.iloc[i]
            price = float(row["close"])
            volume = float(row["volume"])
            regime = self.context.detect_market_regime(df.iloc[:i+1])  # rolling regime

            # Fast Path (of LLM fallback) voor signaal
            fast_result = self.fast_path.run(df.iloc[:i+1], price, regime)

            if position == 0 and fast_result["signal"] in ["BUY", "SELL"] and fast_result["confidence"] > self.context.MIN_CONFLUENCE:
                qty = self.context.calculate_adaptive_risk_and_qty(price, regime, fast_result["stop"])
                side = fast_result["signal"]

                # Slippage + partial fill
                slippage = self._calculate_slippage(price, volume, regime, side)
                entry_price_real = price + slippage
                filled_qty, fill_price = self._simulate_partial_fill(qty, entry_price_real, volume)

                if filled_qty > 0:
                    position = filled_qty if side == "BUY" else -filled_qty
                    entry_price = fill_price
                    commission = self._apply_commission(abs(filled_qty), "entry")
                    equity -= commission
                    trades.append({
                        "ts": row.name,
                        "signal": side,
                        "entry": entry_price,
                        "qty": filled_qty,
                        "slippage": slippage,
                        "partial": filled_qty != qty
                    })

            # Exit check
            if position != 0:
                stop = fast_result.get("stop", 0)
                target = fast_result.get("target", 0)
                hit_stop = (position > 0 and price <= stop) or (position < 0 and price >= stop)
                hit_target = (position > 0 and price >= target) or (position < 0 and price <= target)

                if hit_stop or hit_target:
                    exit_price = price
                    # Exit slippage + commission
                    exit_slip = self._calculate_slippage(exit_price, volume, regime, "SELL" if position > 0 else "BUY")
                    exit_price_real = exit_price + exit_slip
                    pnl = (exit_price_real - entry_price) * position * 5.0
                    commission = self._apply_commission(abs(position), "exit")
                    equity += pnl - commission

                    pnl_history.append(pnl)
                    equity_curve.append(equity)

                    trades[-1].update({
                        "exit": exit_price_real,
                        "pnl": pnl,
                        "exit_slip": exit_slip
                    })

                    position = 0
                    entry_price = 0.0

            equity_curve.append(equity)

        # Metrics
        if not pnl_history:
            return {"trades": 0, "sharpe": 0, "winrate": 0, "maxdd": 0}

        pnl_array = np.array(pnl_history)
        sharpe = (np.mean(pnl_array) / (np.std(pnl_array) + 1e-8)) * np.sqrt(252)
        winrate = np.mean(pnl_array > 0)
        equity_arr = np.array(equity_curve)
        maxdd = min((np.maximum.accumulate(equity_arr) - equity_arr) / np.maximum.accumulate(equity_arr)) * 100

        self.logger.info(f"REAL_BACKTEST_COMPLETE,trades={len(pnl_history)},sharpe={sharpe:.2f},winrate={winrate:.1%},maxdd={maxdd:.1f}%")

        return {
            "sharpe": round(sharpe, 2),
            "winrate": round(winrate, 3),
            "maxdd": round(maxdd, 1),
            "trades": len(pnl_history),
            "avg_pnl": round(np.mean(pnl_array), 1),
            "total_pnl": round(np.sum(pnl_array), 1),
            "equity_curve": equity_curve[-200:],
            "trades_detail": trades[-50:]  # laatste 50 voor journal
        }

    def monte_carlo(self, snapshot: pd.DataFrame, runs: int = 1000) -> Dict:
        """1000 runs met noise + gap events"""
        results = []
        base = snapshot.copy()
        for _ in range(runs):
            noisy = base.copy()
            noise = np.random.normal(0, 0.0008, len(noisy)) * noisy["close"]  # 0.08% noise
            noisy["close"] += noise
            noisy["high"] += abs(noise) * 1.2
            noisy["low"] += noise * 0.8
            res = self.run_backtest_on_snapshot(noisy)
            results.append(res)
        return {
            "mean_sharpe": np.mean([r["sharpe"] for r in results]),
            "median_maxdd": np.median([r["maxdd"] for r in results]),
            "worst_maxdd": max([r["maxdd"] for r in results]),
            "winrate_95pct": np.percentile([r["winrate"] for r in results], 5)
        }
