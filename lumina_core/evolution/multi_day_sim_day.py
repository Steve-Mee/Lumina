"""Day-level trade simulation helpers for MultiDaySimRunner."""
from __future__ import annotations

import hashlib
import json
import logging
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .bot_stress_choices import resolve_ohlc_reality_stress_enabled
from .dna_registry import PolicyDNA
from .reality_generator import build_parallel_reports, stress_simulator_ohlc
from .multi_day_sim_types import ShadowFill, SimResult, stable_seed as _stable_seed

logger = logging.getLogger(__name__)

class MultiDaySimDayMixin:
    """Per-day trade simulation and cost helpers."""

    def _simulate_day_trade(
        self,
        *,
        day_ticks: list[dict[str, Any]],
        variant: PolicyDNA,
        variant_focus: str,
        detected_regime: str,
        rng: random.Random,
    ) -> dict[str, Any]:
        first = day_ticks[0]
        last = day_ticks[-1]
        open_px = float(first.get("last", 0.0) or 0.0)
        close_px = float(last.get("last", open_px) or open_px)
        highs = [float(t.get("last", open_px) or open_px) for t in day_ticks]
        day_high = max(highs) if highs else open_px
        day_low = min(highs) if highs else open_px
        day_range = max(0.25, day_high - day_low)

        focus = str(variant_focus or "neutral").lower()
        regime = str(detected_regime or "NEUTRAL").lower()
        trend_up = close_px >= open_px
        if "range" in focus:
            side = -1 if trend_up else 1
        elif "trend" in focus or "trend" in regime:
            side = 1 if trend_up else -1
        elif "vol" in focus:
            side = 1 if rng.random() >= 0.5 else -1
        else:
            side = 1 if trend_up else -1

        qty = max(1, min(3, int(1 + round(float(getattr(variant, "mutation_rate", 0.0) or 0.0) * 4.0))))
        stop_distance = max(0.25, day_range * 0.35)
        target_distance = max(0.25, day_range * 0.60)

        entry_price = float(first.get("ask", open_px) if side > 0 else first.get("bid", open_px))
        stop_price = entry_price - stop_distance if side > 0 else entry_price + stop_distance
        target_price = entry_price + target_distance if side > 0 else entry_price - target_distance

        exit_price = close_px
        for tick in day_ticks[1:]:
            bid = float(tick.get("bid", tick.get("last", close_px)) or close_px)
            ask = float(tick.get("ask", tick.get("last", close_px)) or close_px)
            mark = bid if side > 0 else ask
            if side > 0 and mark <= stop_price:
                exit_price = stop_price
                break
            if side > 0 and mark >= target_price:
                exit_price = target_price
                break
            if side < 0 and mark >= stop_price:
                exit_price = stop_price
                break
            if side < 0 and mark <= target_price:
                exit_price = target_price
                break

        point_value = self._point_value()
        pnl = (exit_price - entry_price) * float(side) * float(qty) * float(point_value)
        commission = self._commission_cost(qty=qty)
        net_pnl = float(pnl - commission)

        return {
            "side": "BUY" if side > 0 else "SELL",
            "qty": qty,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": net_pnl,
        }

    def _point_value(self) -> float:
        engine = getattr(self.market_data_service, "engine", None)
        valuation = getattr(engine, "valuation_engine", None)
        instrument = str(getattr(getattr(engine, "config", None), "instrument", "MES") or "MES")
        if valuation is not None and hasattr(valuation, "point_value"):
            try:
                return float(valuation.point_value(instrument))
            except Exception:
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/evolution/multi_day_sim_runner.py:678"
                )
                return 5.0
        return 5.0

    def _commission_cost(self, *, qty: int) -> float:
        engine = getattr(self.market_data_service, "engine", None)
        valuation = getattr(engine, "valuation_engine", None)
        instrument = str(getattr(getattr(engine, "config", None), "instrument", "MES") or "MES")
        if valuation is not None and hasattr(valuation, "commission_dollars"):
            try:
                return float(valuation.commission_dollars(symbol=instrument, quantity=int(qty), sides=2))
            except Exception:
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/evolution/multi_day_sim_runner.py:689"
                )
                return float(qty) * 2.58
        return float(qty) * 2.58
