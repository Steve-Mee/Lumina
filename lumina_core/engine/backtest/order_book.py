"""Order Book Replay — realistic bid/ask spread + market impact simulation.

Replaces plain Gaussian slippage with a physics-based model that accounts for:

  1. ATR-scaled half-spread  — wider in volatile regimes
  2. Time-of-day liquidity   — open/close spreads are 2-3× midday
  3. Power-law market impact — Almgren-Chriss simplified (alpha * (Q/ADV)^beta)
  4. Bid-ask bounce          — round-trip cost from crossing the spread twice
  5. Regime overlay          — HIGH_VOLATILITY adds an extra spread multiplier

References:
  - Almgren & Chriss (2001): Optimal execution of portfolio transactions
  - de Prado (2018): Advances in Financial Machine Learning, ch. 9

Design:
  - Pure functions with no side-effects; easy to unit-test.
  - All methods are deterministic given the same inputs.
  - ATR is computed inline from a rolling window of bars if not provided.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Final

# Minimum slippage floor in ticks to avoid unrealistically clean fills.
_MIN_SLIPPAGE_TICKS: Final[float] = 0.5

# Default ATR window (bars) used when bars_window is provided.
_DEFAULT_ATR_WINDOW: Final[int] = 14

# Regime-specific spread multipliers on top of base spread.
_REGIME_SPREAD_MULTIPLIERS: Final[dict[str, float]] = {
    "HIGH_VOLATILITY": 2.5,
    "NEWS_DRIVEN": 2.0,
    "ROLLOVER": 1.8,
    "LOW_LIQUIDITY": 3.0,
    "TRENDING": 1.1,
    "RANGING": 1.0,
    "LOW_VOL": 0.9,
    "NEUTRAL": 1.0,
}


def compute_atr(bars: list[dict[str, Any]], window: int = _DEFAULT_ATR_WINDOW) -> float:
    """Compute the Average True Range from the last *window* bars.

    True Range = max(high-low, |high-prev_close|, |low-prev_close|)

    Returns 1.0 (one tick equivalent) when there are too few bars.
    """
    if len(bars) < 2:
        return 1.0

    recent = bars[-window - 1:]
    trs: list[float] = []
    for i in range(1, len(recent)):
        prev_close = float(recent[i - 1].get("close", recent[i - 1].get("last", 0.0)))
        high = float(recent[i].get("high", 0.0)) or prev_close
        low = float(recent[i].get("low", 0.0)) or prev_close
        if high <= 0 or low <= 0 or prev_close <= 0:
            continue
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    if not trs:
        return 1.0
    return float(statistics.mean(trs[-window:]))


def detect_time_period(bar: dict[str, Any]) -> str:
    """Detect 'open', 'midday', or 'close' from a bar's timestamp.

    Falls back to 'midday' when timestamp is absent or unparsable.
    The US regular session is 09:30–16:00 ET.
    """
    ts_raw = bar.get("timestamp") or bar.get("ts") or bar.get("date")
    if ts_raw is None:
        return "midday"
    try:
        from datetime import datetime, timezone
        ts_str = str(ts_raw).replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        # Convert to approximate ET offset (UTC-4 / UTC-5; use -4 for simplicity).
        hour_et = (dt.hour - 4) % 24
        minute = dt.minute
        time_frac = hour_et + minute / 60.0
        if 9.5 <= time_frac < 10.0:    # 09:30–10:00 ET
            return "open"
        if 15.5 <= time_frac < 16.0:   # 15:30–16:00 ET
            return "close"
        return "midday"
    except Exception:
        return "midday"


@dataclass(slots=True)
class OrderBookReplayV2:
    """Physics-based order book replay model.

    Parameters
    ----------
    spread_atr_ratio : float
        Fraction of ATR used as the base half-spread (default 0.10 = 10% of ATR).
    market_impact_alpha : float
        Almgren-Chriss alpha coefficient.
    market_impact_beta : float
        Almgren-Chriss beta exponent (0.5 = square-root law).
    time_of_day_multipliers : dict
        Keyed by 'open' / 'midday' / 'close'.
    bid_ask_bounce : bool
        If True, includes a full bid-ask round-trip cost (2 × half-spread).
    """

    spread_atr_ratio: float = 0.10
    market_impact_alpha: float = 0.50
    market_impact_beta: float = 0.60
    time_of_day_multipliers: dict[str, float] = field(default_factory=lambda: {
        "open": 2.5,
        "midday": 1.0,
        "close": 2.0,
    })
    bid_ask_bounce: bool = True

    def half_spread_ticks(
        self,
        atr: float,
        tick_size: float = 0.25,
        *,
        time_period: str = "midday",
        regime: str = "NEUTRAL",
    ) -> float:
        """Compute half-spread in ticks.

        Spread (ticks) = max(1, (ATR × spread_ratio × tod_mult × regime_mult) / tick_size)
        """
        if atr <= 0 or tick_size <= 0:
            return 1.0
        tod_mult = self.time_of_day_multipliers.get(time_period, 1.0)
        regime_mult = _REGIME_SPREAD_MULTIPLIERS.get(regime.upper(), 1.0)
        spread_points = max(tick_size, atr * self.spread_atr_ratio * tod_mult * regime_mult)
        return max(1.0, spread_points / tick_size)

    def market_impact_ticks(
        self,
        quantity: float,
        avg_volume: float,
        tick_size: float = 0.25,
    ) -> float:
        """Almgren-Chriss simplified power-law market impact.

        impact_ticks = alpha × (qty / ADV)^beta / tick_size

        Returns 0.0 when avg_volume ≤ 0 or quantity ≤ 0.
        """
        if avg_volume <= 0 or quantity <= 0:
            return 0.0
        volume_ratio = max(float(quantity), 0.0) / max(float(avg_volume), 1.0)
        impact_points = self.market_impact_alpha * (volume_ratio ** self.market_impact_beta)
        return max(0.0, impact_points / tick_size)

    def total_slippage_ticks(
        self,
        bar: dict[str, Any],
        atr: float,
        quantity: float = 1.0,
        avg_volume: float = 1000.0,
        tick_size: float = 0.25,
        *,
        time_period: str | None = None,
        regime: str = "NEUTRAL",
    ) -> float:
        """Return total slippage in ticks for one side of a trade.

        If time_period is None, it is inferred from bar["timestamp"].

        Components:
          - half_spread × (2 if bid_ask_bounce else 1)
          - market_impact

        The factor of 2 on spread captures the full round-trip cost
        (we pay spread on entry and again on exit).
        """
        period = time_period or detect_time_period(bar)
        spread = self.half_spread_ticks(
            atr, tick_size, time_period=period, regime=regime
        )
        impact = self.market_impact_ticks(quantity, avg_volume, tick_size)
        bounce_mult = 2.0 if self.bid_ask_bounce else 1.0
        return max(_MIN_SLIPPAGE_TICKS, spread * bounce_mult + impact)


@dataclass(slots=True)
class DynamicSlippageModel:
    """Per-bar composite slippage model that wraps OrderBookReplayV2.

    Computes ATR inline from a rolling window of bars, infers time-of-day from
    bar timestamps, and applies regime-aware spread multipliers.

    This is the primary slippage interface used by BacktesterEngine._run_single().
    """

    replay: OrderBookReplayV2 = field(default_factory=OrderBookReplayV2)
    atr_window: int = _DEFAULT_ATR_WINDOW
    tick_size: float = 0.25  # MES default

    def slippage_for_bar(
        self,
        bar: dict[str, Any],
        bar_history: list[dict[str, Any]],
        *,
        quantity: float = 1.0,
        avg_volume: float = 1000.0,
        regime: str = "NEUTRAL",
        time_period: str | None = None,
    ) -> float:
        """Compute total slippage in ticks for a trade on *bar*.

        Args:
            bar:          The bar on which the trade executes.
            bar_history:  Recent bars (including *bar*) used to compute ATR.
            quantity:     Number of contracts.
            avg_volume:   Average daily volume for impact scaling.
            regime:       Market regime label from RegimeDetector.
            time_period:  Override 'open'/'midday'/'close' (inferred if None).

        Returns:
            Total slippage in ticks (≥ 0.5).
        """
        atr = compute_atr(bar_history, window=self.atr_window)
        return self.replay.total_slippage_ticks(
            bar=bar,
            atr=atr,
            quantity=quantity,
            avg_volume=avg_volume,
            tick_size=self.tick_size,
            time_period=time_period,
            regime=regime,
        )

    def slippage_dollars(
        self,
        bar: dict[str, Any],
        bar_history: list[dict[str, Any]],
        *,
        quantity: float = 1.0,
        avg_volume: float = 1000.0,
        regime: str = "NEUTRAL",
        point_value: float = 5.0,
    ) -> float:
        """Slippage converted to dollars using instrument point_value."""
        ticks = self.slippage_for_bar(
            bar, bar_history, quantity=quantity, avg_volume=avg_volume, regime=regime
        )
        return ticks * self.tick_size * point_value

    def calibrate_from_history(self, real_fills: list[dict[str, Any]]) -> "DynamicSlippageModel":
        """Adjust spread_atr_ratio to match observed real fill slippage.

        Each entry in real_fills must have:
          - 'slippage_ticks': observed slippage on the fill
          - 'atr': ATR at the time of the fill

        Returns self for chaining.
        """
        if not real_fills:
            return self
        observed_ratios: list[float] = []
        for fill in real_fills:
            slip = float(fill.get("slippage_ticks", 0.0))
            atr = float(fill.get("atr", 0.0))
            if atr > 0 and slip > 0:
                observed_ratios.append(slip * self.tick_size / atr)
        if observed_ratios:
            calibrated = statistics.median(observed_ratios)
            self.replay.spread_atr_ratio = max(0.01, min(1.0, calibrated))
        return self
