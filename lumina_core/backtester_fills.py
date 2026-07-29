"""Backtester fill / slippage simulation + OrderBookReplay.

Extracted from ``backtester_engine`` (Wave B2 PR-C0).
Canonical import: ``from lumina_core.backtester_engine import OrderBookReplay``.
"""
from __future__ import annotations

import logging
import random
import statistics
from typing import Any

logger = logging.getLogger(__name__)


class BacktesterFillsMixin:
    """Single-path fill simulation helpers for ``BacktesterEngine``."""

    __slots__ = ()

    def _run_single(
        self,
        snapshot: list[dict[str, Any]],
        *,
        rng: random.Random,
        noise_std_points: float,
        min_confluence_override: float | None = None,
        slippage_scale: float = 1.0,
        include_gap_events: bool = False,
        gap_event_prob: float = 0.002,
        gap_std_points: float = 2.0,
        use_dynamic_slippage: bool = True,
    ) -> dict[str, Any]:
        pnl_values: list[float] = []
        equity: list[float] = [50000.0]
        slippage_ticks: list[float] = []
        commission_paid = 0.0
        gap_events = 0
        regime_attribution: dict[str, dict[str, float]] = {}
        regime_counts: dict[str, int] = {}

        position = 0
        entry_price = 0.0
        entry_regime = "NEUTRAL"
        pending_side = 0
        pending_age = 0

        dream_snapshot = self.app.get_current_dream_snapshot()
        signal = str(dream_snapshot.get("signal", "HOLD"))
        confluence = float(dream_snapshot.get("confluence_score", 0.0))
        min_confluence = float(
            min_confluence_override if min_confluence_override is not None else getattr(self.app, "MIN_CONFLUENCE", 0.8)
        )

        for i in range(60, len(snapshot)):
            row = snapshot[i]
            raw_price = float(row.get("close", row.get("last", 0.0)))
            if raw_price <= 0:
                continue

            price = raw_price + rng.gauss(0.0, noise_std_points)
            if include_gap_events and rng.random() < gap_event_prob:
                price += rng.gauss(0.0, gap_std_points)
                gap_events += 1
            volume = float(row.get("volume", 0.0))
            recent = snapshot[max(0, i - 30) : i]
            bar_history = snapshot[max(0, i - self.dynamic_slippage.atr_window - 1) : i + 1]
            avg_volume = self._avg_volume(recent)
            regime = self._regime_from_snapshot(snapshot[: i + 1])
            regime_label = self._normalize_regime(regime)
            regime_counts[regime_label] = regime_counts.get(regime_label, 0) + 1

            if position == 0 and pending_side == 0 and signal in {"BUY", "SELL"} and confluence > min_confluence:
                pending_side = 1 if signal == "BUY" else -1
                pending_age = 0

            if pending_side != 0:
                pending_age += 1
                if self._queue_filled(rng, volume, avg_volume, pending_age, regime):
                    if use_dynamic_slippage:
                        slip_ticks = (
                            self.dynamic_slippage.slippage_for_bar(
                                row,
                                bar_history,
                                quantity=1.0,
                                avg_volume=avg_volume,
                                regime=regime_label,
                            )
                            * slippage_scale
                        )
                    else:
                        slip_ticks = self._slippage_ticks(volume, avg_volume, regime, slippage_scale=slippage_scale)
                    slippage_ticks.append(slip_ticks)
                    fill_price = self._apply_entry_fill(price, pending_side, slip_ticks)
                    position = pending_side
                    entry_price = fill_price
                    entry_regime = regime_label
                    pending_side = 0
                    pending_age = 0
                elif pending_age > 3:
                    pending_side = 0
                    pending_age = 0

            if position != 0:
                stop = float(dream_snapshot.get("stop", 0.0))
                target = float(dream_snapshot.get("target", 0.0))
                hit_stop = (position > 0 and stop > 0 and price <= stop) or (
                    position < 0 and stop > 0 and price >= stop
                )
                hit_target = (position > 0 and target > 0 and price >= target) or (
                    position < 0 and target > 0 and price <= target
                )

                if hit_stop or hit_target:
                    if use_dynamic_slippage:
                        slip_ticks = (
                            self.dynamic_slippage.slippage_for_bar(
                                row,
                                bar_history,
                                quantity=1.0,
                                avg_volume=avg_volume,
                                regime=regime_label,
                            )
                            * slippage_scale
                        )
                    else:
                        slip_ticks = self._slippage_ticks(volume, avg_volume, regime, slippage_scale=slippage_scale)
                    slippage_ticks.append(slip_ticks)
                    exit_price = self._apply_exit_fill(price, position, slip_ticks)

                    gross = (exit_price - entry_price) * position * self.point_value
                    trade_fee = 2.0 * self._commission_dollars_one_side()
                    commission_paid += trade_fee
                    net = gross - trade_fee

                    pnl_values.append(net)
                    equity.append(equity[-1] + net)
                    bucket = regime_attribution.setdefault(
                        entry_regime,
                        {"trades": 0.0, "wins": 0.0, "net_pnl": 0.0, "avg_pnl": 0.0, "winrate": 0.0},
                    )
                    bucket["trades"] += 1.0
                    if net > 0:
                        bucket["wins"] += 1.0
                    bucket["net_pnl"] += float(net)

                    position = 0
                    entry_price = 0.0
                    entry_regime = "NEUTRAL"

        for stats in regime_attribution.values():
            trades = max(1.0, stats["trades"])
            stats["avg_pnl"] = float(stats["net_pnl"] / trades)
            stats["winrate"] = float(stats["wins"] / trades)

        sharpe = self._sharpe(pnl_values)
        winrate = self._winrate(pnl_values)
        maxdd = self._max_drawdown_pct(equity)
        avg_slip = statistics.mean(slippage_ticks) if slippage_ticks else 0.0

        return {
            "trades": len(pnl_values),
            "sharpe": sharpe,
            "winrate": winrate,
            "maxdd": maxdd,
            "net_pnl": float(sum(pnl_values)),
            "commission_paid": float(commission_paid),
            "avg_slippage_ticks": float(avg_slip),
            "equity_curve": [float(x) for x in equity],
            "regime_attribution": regime_attribution,
            "regime_summary": regime_counts,
            "gap_events": int(gap_events),
        }

    def _regime_from_snapshot(self, rows: list[dict[str, Any]]) -> str:
        try:
            if hasattr(self.app, "detect_market_regime"):
                import pandas as pd

                df = pd.DataFrame(rows)
                if not df.empty and {"open", "high", "low", "close", "volume"}.issubset(df.columns):
                    return str(self.app.detect_market_regime(df))
        except Exception:
            logger.exception("BacktesterEngine failed to derive regime from snapshot; defaulting to NEUTRAL")
        return "NEUTRAL"

    @staticmethod
    def _avg_volume(rows: list[dict[str, Any]]) -> float:
        vols = [float(r.get("volume", 0.0)) for r in rows if float(r.get("volume", 0.0)) > 0.0]
        return statistics.mean(vols) if vols else 1.0

    def _queue_filled(self, rng: random.Random, volume: float, avg_volume: float, age: int, regime: str) -> bool:
        return self.valuation_engine.should_fill_order(
            rng=rng,
            volume=volume,
            avg_volume=avg_volume,
            pending_age=age,
            regime=regime,
        )

    def _slippage_ticks(self, volume: float, avg_volume: float, regime: str, slippage_scale: float) -> float:
        return self.valuation_engine.slippage_ticks(
            volume=volume,
            avg_volume=avg_volume,
            regime=regime,
            slippage_scale=slippage_scale,
        )

    @staticmethod
    def _normalize_regime(raw: str) -> str:
        text = str(raw).upper()
        if any(x in text for x in ("TREND", "BREAKOUT", "MOMENTUM")):
            return "TRENDING"
        if any(x in text for x in ("RANGE", "SIDEWAYS", "MEAN")):
            return "RANGING"
        if any(x in text for x in ("VOLATILE", "CHAOS", "HIGH_VOL", "HIGH_VOLATILITY")):
            return "HIGH_VOLATILITY"
        if "NEWS" in text:
            return "NEWS_DRIVEN"
        if "ROLLOVER" in text:
            return "ROLLOVER"
        if "LOW_LIQ" in text:
            return "LOW_LIQUIDITY"
        if any(x in text for x in ("LOW_VOL", "CALM")):
            return "LOW_VOL"
        return "NEUTRAL"

    def _apply_entry_fill(self, price: float, side: int, slip_ticks: float) -> float:
        instrument = str(getattr(self.app.engine.config, "instrument", "MES"))
        return self.valuation_engine.apply_entry_fill(
            symbol=instrument,
            price=price,
            side=side,
            slippage_ticks=slip_ticks,
        )

    def _apply_exit_fill(self, price: float, side: int, slip_ticks: float) -> float:
        instrument = str(getattr(self.app.engine.config, "instrument", "MES"))
        return self.valuation_engine.apply_exit_fill(
            symbol=instrument,
            price=price,
            side=side,
            slippage_ticks=slip_ticks,
        )

    def _commission_dollars_one_side(self) -> float:
        instrument = str(getattr(self.app.engine.config, "instrument", "MES"))
        return self.valuation_engine.commission_dollars(symbol=instrument, quantity=1, sides=1)


# ---------------------------------------------------------------------------
# P3: OrderBookReplay — ATR-based bid/ask spread simulator
# ---------------------------------------------------------------------------


class OrderBookReplay:
    """Simulates realistic bid-ask spreads and market impact from OHLCV bars.

    Replaces pure-Gaussian slippage with a model that accounts for:
      - Intraday liquidity patterns (open/midday/close spread multipliers)
      - ATR-scaled spread width (wider in volatile regimes)
      - Power-law market impact for position sizing (Almgren-Chriss simplified)

    Designed to be used inside ``BacktesterEngine._run_single()`` as a
    drop-in replacement for ``ValuationEngine.slippage_ticks()``.
    """

    def __init__(
        self,
        *,
        spread_atr_ratio: float = 0.10,
        market_impact_alpha: float = 0.5,
        market_impact_beta: float = 0.6,
        time_of_day_multipliers: dict[str, float] | None = None,
    ) -> None:
        self.spread_atr_ratio = float(spread_atr_ratio)
        self.market_impact_alpha = float(market_impact_alpha)
        self.market_impact_beta = float(market_impact_beta)
        self.time_of_day_multipliers: dict[str, float] = time_of_day_multipliers or {
            "open": 2.5,  # First 30 min — wide spreads
            "midday": 1.0,  # 10:30–14:00 EST — normal liquidity
            "close": 2.0,  # Last 30 min — wider again
        }

    def spread_ticks(
        self,
        bar: dict[str, Any],
        atr: float,
        tick_size: float = 0.25,
        *,
        time_period: str = "midday",
    ) -> float:
        """Estimate half-spread in ticks for the given bar.

        Args:
            bar:         OHLCV dict with 'high', 'low', 'close' keys.
            atr:         Average True Range in price points.
            tick_size:   Instrument tick size (0.25 for MES).
            time_period: 'open', 'midday', or 'close'.

        Returns:
            Half-spread in ticks (add to entry, subtract from exit).
        """
        if atr <= 0 or tick_size <= 0:
            return 1.0

        spread_points = max(tick_size, atr * self.spread_atr_ratio)
        multiplier = self.time_of_day_multipliers.get(time_period, 1.0)
        half_spread_ticks = (spread_points * multiplier) / tick_size
        return max(1.0, float(half_spread_ticks))

    def market_impact_ticks(
        self,
        quantity: float,
        avg_volume: float,
        tick_size: float = 0.25,
    ) -> float:
        """Estimate market-impact cost in ticks using a power-law model.

        Impact = alpha * (qty / avg_volume) ^ beta

        Returns 0.0 when avg_volume <= 0 (e.g., synthetic data).
        """
        if avg_volume <= 0 or quantity <= 0:
            return 0.0

        volume_ratio = float(quantity) / max(float(avg_volume), 1.0)
        impact_points = self.market_impact_alpha * (volume_ratio**self.market_impact_beta)
        return max(0.0, impact_points / tick_size)

    def total_slippage_ticks(
        self,
        bar: dict[str, Any],
        atr: float,
        quantity: float = 1.0,
        avg_volume: float = 1000.0,
        tick_size: float = 0.25,
        *,
        time_period: str = "midday",
    ) -> float:
        """Combined half-spread + market-impact in ticks."""
        spread = self.spread_ticks(bar, atr, tick_size, time_period=time_period)
        impact = self.market_impact_ticks(quantity, avg_volume, tick_size)
        return spread + impact
