"""True backtest and tick-proxy paths for MultiDaySimRunner."""
from __future__ import annotations

import json
import logging
import random
from typing import Any

import pandas as pd

from .dna_registry import PolicyDNA
from .multi_day_sim_types import ShadowFill

logger = logging.getLogger(__name__)

class MultiDaySimBacktestMixin:
    """True backtest + tick-proxy fitness paths."""

    def _calculate_tick_proxy_daily_pnl(
        self,
        ticks: list[dict[str, Any]],
        target_days: int,
        baseline_equity: float,
        variant: PolicyDNA,
        rng: random.Random,
    ) -> list[float]:
        """Heuristic daily PnL from historical tick bars (evolution / shadow SIM).

        Not broker-confirmed ``economic_pnl``; uses intraday range heuristics only.
        """
        pnl_values: list[float] = []
        if not ticks:
            return pnl_values

        # Group ticks by day
        ticks_by_day: dict[str, list[dict[str, Any]]] = {}
        for tick in ticks:
            try:
                ts_str = tick.get("timestamp", "")
                if not ts_str:
                    continue
                day_key = str(ts_str)[:10]  # YYYY-MM-DD
                if day_key not in ticks_by_day:
                    ticks_by_day[day_key] = []
                ticks_by_day[day_key].append(tick)
            except Exception:
                logging.exception(
                    "Unhandled broad exception fallback in lumina_core/evolution/multi_day_sim_runner.py:423"
                )
                continue

        sorted_days = sorted(ticks_by_day.keys())[-target_days:]

        # Extract variant win_rate if available; otherwise use reasonable default
        variant_dict = getattr(variant, "__dict__", {}) if hasattr(variant, "__dict__") else {}
        variant_win_rate = float(variant_dict.get("win_rate", 0.52) or 0.52)
        variant_win_rate = max(0.45, min(0.65, variant_win_rate))  # Clamp to realistic range

        for day_key in sorted_days:
            day_ticks = ticks_by_day[day_key]
            if len(day_ticks) < 2:
                pnl_values.append(0.0)
                continue

            # Calculate intraday price moves and derive daily PnL
            entry_price = float(day_ticks[0].get("last", 100.0))
            max_price = max(float(t.get("high", t.get("last", entry_price))) for t in day_ticks)
            min_price = min(float(t.get("low", t.get("last", entry_price))) for t in day_ticks)

            # Probabilistic win/loss based on variant win_rate
            is_win = rng.random() < variant_win_rate
            if is_win:
                # Wins: capture 40-60% of daily range
                range_pnl = (max_price - min_price) * rng.uniform(0.4, 0.6)
                daily_pnl = range_pnl * rng.uniform(0.9, 1.1)
            else:
                # Losses: lose 20-40% of daily range
                range_loss = (max_price - min_price) * rng.uniform(0.2, 0.4)
                daily_pnl = -range_loss * rng.uniform(0.9, 1.1)

            pnl_values.append(float(daily_pnl))

        return pnl_values

    def _run_true_backtest(
        self,
        *,
        ticks: list[dict[str, Any]],
        target_days: int,
        baseline_equity: float,
        variant: PolicyDNA,
        rng: random.Random,
        shadow_mode: bool,
    ) -> dict[str, Any]:
        daily_bars = self._group_ticks_by_day(ticks=ticks)
        day_keys = sorted(daily_bars.keys())[-max(1, int(target_days)) :]

        equity = float(baseline_equity)
        peak_equity = float(baseline_equity)
        max_dd_ratio = 0.0
        regime_bonus = 0.0
        fills: list[ShadowFill] = []
        pnl_values: list[float] = []

        variant_focus = self._variant_regime_focus(variant)

        for idx, day_key in enumerate(day_keys, start=1):
            day_ticks = daily_bars.get(day_key, [])
            if len(day_ticks) < 2:
                pnl_values.append(0.0)
                continue

            day_df = self._ticks_to_ohlc_frame(day_ticks)
            day_regime = self._detect_day_regime(day_df=day_df)
            regime_bonus += self._regime_alignment_score(variant_focus=variant_focus, detected_regime=day_regime)

            trade = self._simulate_day_trade(
                day_ticks=day_ticks,
                variant=variant,
                variant_focus=variant_focus,
                detected_regime=day_regime,
                rng=rng,
            )
            day_pnl = float(trade.get("pnl", 0.0) or 0.0)
            pnl_values.append(day_pnl)

            equity += day_pnl
            peak_equity = max(peak_equity, equity)
            drawdown = max(0.0, peak_equity - equity)
            max_dd_ratio = max(max_dd_ratio, drawdown / max(1.0, baseline_equity))

            if shadow_mode:
                fills.append(
                    ShadowFill(
                        day_index=idx,
                        side=str(trade.get("side", "HOLD")),
                        qty=int(trade.get("qty", 1) or 1),
                        entry_price=float(trade.get("entry_price", 0.0) or 0.0),
                        exit_price=float(trade.get("exit_price", 0.0) or 0.0),
                        pnl=day_pnl,
                        reason=f"shadow_true_backtest_{day_regime.lower()}",
                    )
                )

        normalized_regime_bonus = max(-0.75, min(0.75, regime_bonus / max(1, len(day_keys))))
        return {
            "daily_pnl": pnl_values,
            "max_drawdown_ratio": max_dd_ratio,
            "regime_fit_bonus": normalized_regime_bonus,
            "fills": fills,
        }

    @staticmethod
    def _group_ticks_by_day(*, ticks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for tick in ticks:
            ts = str(tick.get("timestamp", "") or "")
            if len(ts) < 10:
                continue
            day_key = ts[:10]
            grouped.setdefault(day_key, []).append(tick)
        return grouped

    def _variant_regime_focus(self, variant: PolicyDNA) -> str:
        raw_content = str(getattr(variant, "content", "") or "")
        payload: dict[str, Any] = {}
        try:
            loaded = json.loads(raw_content)
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/multi_day_sim_runner.py:545")
            payload = {}

        explicit = str(payload.get("regime_focus", "") or "").strip().lower()
        if explicit:
            return explicit
        text = raw_content.lower()
        if "trend" in text:
            return "trending"
        if "range" in text:
            return "ranging"
        if "volatility" in text or "volatile" in text:
            return "high_volatility"
        return "neutral"

    def _ticks_to_ohlc_frame(self, day_ticks: list[dict[str, Any]]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for tick in day_ticks:
            px = float(tick.get("last", 0.0) or 0.0)
            if px <= 0.0:
                continue
            rows.append(
                {
                    "timestamp": tick.get("timestamp"),
                    "open": px,
                    "high": float(tick.get("high", px) or px),
                    "low": float(tick.get("low", px) or px),
                    "close": px,
                    "volume": float(tick.get("volume", 0.0) or 0.0),
                }
            )
        if not rows:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        return pd.DataFrame(rows)

    def _detect_day_regime(self, *, day_df: pd.DataFrame) -> str:
        engine = getattr(self.market_data_service, "engine", None)
        if engine is not None and hasattr(engine, "detect_market_regime") and len(day_df) > 4:
            try:
                regime = engine.detect_market_regime(day_df)
                return str(regime or "NEUTRAL").upper()
            except Exception:
                logger.exception("MultiDaySimRunner failed to detect day regime; defaulting to NEUTRAL")
        return "NEUTRAL"

    @staticmethod
    def _regime_alignment_score(*, variant_focus: str, detected_regime: str) -> float:
        focus = str(variant_focus or "neutral").lower()
        regime = str(detected_regime or "NEUTRAL").lower()
        if focus == "neutral":
            return 0.02
        if ("trend" in focus and "trend" in regime) or ("range" in focus and "rang" in regime):
            return 0.12
        if "vol" in focus and ("vol" in regime or "news" in regime):
            return 0.12
        return -0.06

