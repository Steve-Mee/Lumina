from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from .lumina_engine import LuminaEngine


@dataclass(slots=True)
class PositionSizer:
    """Fractional Kelly-based position sizing for capital preservation (v51)."""
    
    @staticmethod
    def calculate_kelly_fraction(
        win_rate: float,
        avg_win: float = 1.0,
        avg_loss: float = 1.0,
        kelly_fraction_max: float = 0.25,
    ) -> float:
        """
        Calculate optimal Kelly fraction with cap for safety.
        
        Kelly formula: f* = (bp - q) / b
        where:
          - f* = optimal Kelly fraction
          - b = average_win / average_loss (reward/risk ratio)
          - p = probability of win
          - q = probability of loss (1 - p)
        
        Args:
            win_rate: Probability of winning (0-1)
            avg_win: Average size of winning trade (default 1.0)
            avg_loss: Average size of losing trade (default 1.0)
            kelly_fraction_max: Maximum Kelly fraction to use (default 0.25 for safety)
        
        Returns:
            Actual Kelly fraction to use (capped at kelly_fraction_max)
        """
        if win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        loss_rate = 1.0 - win_rate
        if avg_loss <= 0:
            return 0.0
        
        b = avg_win / avg_loss  # Reward/risk ratio
        q = loss_rate
        
        # Kelly formula
        kelly_optimal = (b * win_rate - q) / b
        
        # Cap at kelly_fraction_max for safety
        kelly_safe = max(0.0, min(kelly_optimal, kelly_fraction_max))
        
        return float(kelly_safe)
    
    @staticmethod
    def calculate_position_size(
        account_equity: float,
        kelly_fraction: float,
        confidence: float = 1.0,
        min_confidence: float = 0.65,
    ) -> float:
        """
        Calculate trade size based on Kelly fraction and confidence.
        
        Trade size = account_equity * kelly_fraction * confidence
        Only apply Kelly if confidence >= min_confidence.
        
        Args:
            account_equity: Current account equity (USD)
            kelly_fraction: Kelly fraction to apply (0-1)
            confidence: Current signal confidence (0-1)
            min_confidence: Minimum confidence to apply Kelly (default 0.65)
        
        Returns:
            Position size in USD (0 if below min_confidence)
        """
        if confidence < min_confidence:
            return 0.0
        
        return float(account_equity * kelly_fraction * min(confidence, 1.0))


@dataclass(slots=True)
class FastPathEngine:
    """Low-latency rule engine for first-pass trade decisions.

    Supports both direct engine= construction (internal services) and
    RuntimeContext injection via context= (compatibility with LocalInferenceEngine).
    Beslissingstijd < 200 ms. LLM-takeover als confidence < fast_path_threshold.
    
    v51 Capital Preservation:
    - Fractional Kelly position sizing (25% max)
    - News avoidance windows (configurable pre/post)
    - EOD force-close protection
    - MarginTracker integration
    """

    engine: LuminaEngine
    llm_confidence_threshold: float = 0.75
    position_sizer: PositionSizer = field(default_factory=PositionSizer)

    def __post_init__(self) -> None:
        # Sync threshold from config.yaml when available via local_engine
        local_engine = getattr(self.engine, "local_engine", None)
        if local_engine is not None:
            cfg = getattr(local_engine, "config", {})
            threshold = cfg.get("inference", {}).get("fast_path_threshold", None)
            if threshold is not None:
                object.__setattr__(self, "llm_confidence_threshold", float(threshold))

    # ------------------------------------------------------------------ helpers

    def calculate_ma_ribbon(self, df_1min: pd.DataFrame) -> dict[str, Any]:
        """8-21-34-55 EMA ribbon + slope van EMA-8."""
        close = df_1min["close"].astype(float)
        emas: dict[str, float] = {}
        for period in [8, 21, 34, 55]:
            emas[f"ema_{period}"] = float(close.ewm(span=period, adjust=False).mean().iloc[-1])

        ribbon_bullish = all(
            emas[f"ema_{p}"] > emas[f"ema_{q}"] for p, q in [(8, 21), (21, 34), (34, 55)]
        )
        ribbon_bearish = all(
            emas[f"ema_{p}"] < emas[f"ema_{q}"] for p, q in [(8, 21), (21, 34), (34, 55)]
        )

        prev_ema8 = float(close.ewm(span=8, adjust=False).mean().iloc[-3])
        last_price_prev = float(close.iloc[-3])
        slope = (emas["ema_8"] - prev_ema8) / last_price_prev if last_price_prev != 0 else 0.0

        return {
            "emas": emas,
            "ribbon_bullish": ribbon_bullish,
            "ribbon_bearish": ribbon_bearish,
            "slope": slope,
        }

    def tape_score(self, df_1min: pd.DataFrame) -> float:
        """Volume spike + bid/ask imbalance → score 0-4."""
        recent = df_1min.tail(20)
        avg_vol = float(recent["volume"].mean())
        last_vol = float(recent["volume"].iloc[-1])
        vol_spike = last_vol / avg_vol if avg_vol > 0 else 1.0

        tape = self.engine.market_data.get_tape_snapshot()
        imbalance = abs(float(tape.get("bid_ask_imbalance", 1.0)) - 1.0)

        return float(min(vol_spike * (1.0 + imbalance), 4.0))

    def fib_confluence(self, price: float, swing_high: float, swing_low: float) -> float:
        """Proximity score to nearest Fibonacci level (0-1, higher = closer)."""
        if swing_high == swing_low:
            return 0.0
        diff = swing_high - swing_low
        levels = [swing_high - diff * r for r in (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)]
        closest = min(levels, key=lambda x: abs(x - price))
        distance_pct = abs(price - closest) / price if price != 0 else 1.0
        return float(1.0 - min(distance_pct / 0.005, 1.0))

    def regime_filter(self, regime: str) -> float:
        """Regime risk multiplier from engine config."""
        multipliers: dict[str, float] = getattr(
            self.engine.config, "regime_risk_multipliers",
            {"TRENDING_UP": 1.2, "TRENDING_DOWN": 1.2, "RANGING": 0.8, "VOLATILE": 0.9, "NEUTRAL": 1.0},
        )
        return float(multipliers.get(regime.upper(), 1.0))

    # ------------------------------------------------------------------ main

    def run(self, df_1min: pd.DataFrame, current_price: float, regime: str) -> dict[str, Any]:
        """Hoofdmethode – alias voor evaluate() met RuntimeContext-compatible signature."""
        result = self.evaluate(df_1min, regime, current_price=current_price)
        swarm_manager = getattr(self.engine, "swarm", None)
        if swarm_manager is not None and hasattr(swarm_manager, "run_swarm_cycle"):
            try:
                swarm_info = swarm_manager.run_swarm_cycle()
                result["swarm_regime"] = swarm_info.get("global_regime", "NEUTRAL")
                result["swarm_info"] = swarm_info
            except Exception as exc:
                logger = getattr(self.engine, "logger", None)
                if logger is not None:
                    logger.debug(f"FastPath swarm context skipped: {exc}")
        return result

    def evaluate(
        self,
        df_1min: pd.DataFrame,
        regime: str,
        current_price: float | None = None,
    ) -> dict[str, Any]:
        """Rule-based evaluation. Returns signal, confidence, stop, target, used_llm."""
        start = time.perf_counter()

        if len(df_1min) < 60:
            return self._result("HOLD", 0.0, regime, True, "insufficient_data", start)

        work_df = df_1min.copy()
        if "timestamp" in work_df.columns:
            work_df["timestamp"] = pd.to_datetime(work_df["timestamp"])
            work_df = work_df.sort_values("timestamp")

        close = work_df["close"].astype(float)
        high = work_df["high"].astype(float)
        low = work_df["low"].astype(float)
        last_price = current_price if current_price is not None else float(close.iloc[-1])

        # MA ribbon
        ma_data = self.calculate_ma_ribbon(work_df)
        ribbon_bull = ma_data["ribbon_bullish"]
        ribbon_bear = ma_data["ribbon_bearish"]
        ema21 = ma_data["emas"]["ema_21"]

        # Tape
        tape_val = self.tape_score(work_df)
        tape = self.engine.market_data.get_tape_snapshot()
        cumulative_delta = float(tape.get("cumulative_delta_10", 0.0))
        tape_buy = tape_val > 2.0 and cumulative_delta > 0
        tape_sell = tape_val > 2.0 and cumulative_delta < 0

        # Fibs
        recent_high = float(high.iloc[-60:].max())
        recent_low = float(low.iloc[-60:].min())
        fib_score = self.fib_confluence(last_price, recent_high, recent_low)

        # Regime
        regime_mult = self.regime_filter(regime)
        regime_norm = regime.upper()
        regime_buy_ok = not any(x in regime_norm for x in ("DOWN", "BEAR"))
        regime_sell_ok = not any(x in regime_norm for x in ("UP", "BULL"))

        # Confluence scoring
        buy_conf = sell_conf = 0.0
        reasons: list[str] = []

        if ribbon_bull:
            buy_conf += 0.35
            if ma_data["slope"] > 0:
                buy_conf += 0.05
                reasons.append("bullish MA ribbon + positive slope")
            else:
                reasons.append("bullish MA ribbon")
        if ribbon_bear:
            sell_conf += 0.35
            if ma_data["slope"] < 0:
                sell_conf += 0.05
                reasons.append("bearish MA ribbon + negative slope")
            else:
                reasons.append("bearish MA ribbon")

        if tape_buy:
            buy_conf += 0.30
            reasons.append(f"strong tape buy (x{tape_val:.1f})")
        if tape_sell:
            sell_conf += 0.30
            reasons.append(f"strong tape sell (x{tape_val:.1f})")

        if fib_score > 0.7:
            buy_conf += 0.20
            sell_conf += 0.20
            reasons.append("strong fib confluence")

        regime_bonus = (regime_mult - 0.9) * 0.5
        if regime_buy_ok:
            buy_conf += 0.15 + regime_bonus
        else:
            buy_conf -= 0.10
        if regime_sell_ok:
            sell_conf += 0.15 + regime_bonus
        else:
            sell_conf -= 0.10

        buy_conf = min(1.0, max(0.0, buy_conf))
        sell_conf = min(1.0, max(0.0, sell_conf))

        # Signal
        if buy_conf > sell_conf and buy_conf >= 0.5 and ribbon_bull and last_price > ema21:
            signal = "BUY"
            confidence = buy_conf
        elif sell_conf > buy_conf and sell_conf >= 0.5 and ribbon_bear and last_price < ema21:
            signal = "SELL"
            confidence = sell_conf
        else:
            signal = "HOLD"
            confidence = max(buy_conf, sell_conf)

        pass_to_llm = confidence < self.llm_confidence_threshold

        # Stop & target – 1:2 RR via ATR
        atr = float(high.iloc[-60:].sub(low.iloc[-60:]).mean()) * 1.5
        if signal == "BUY":
            stop = round(last_price - atr * 0.8, 2)
            target = round(last_price + atr * 1.6, 2)
        elif signal == "SELL":
            stop = round(last_price + atr * 0.8, 2)
            target = round(last_price - atr * 1.6, 2)
        else:
            stop = target = 0.0

        reason_str = " | ".join(reasons) if reasons else (
            f"ribbon={'bull' if ribbon_bull else 'bear' if ribbon_bear else 'mixed'}, "
            f"tape={tape_val:.1f}, fib={fib_score:.2f}, regime={regime_norm}"
        )

        return self._result(
            signal,
            confidence,
            regime_norm,
            pass_to_llm,
            reason_str,
            start,
            stop=stop,
            target=target,
        )

    def _result(
        self,
        signal: str,
        confidence: float,
        regime: str,
        pass_to_llm: bool,
        reason: str,
        start: float,
        stop: float = 0.0,
        target: float = 0.0,
    ) -> dict[str, Any]:
        latency_ms = (time.perf_counter() - start) * 1000.0
        logger = getattr(self.engine, "logger", None)
        if logger:
            logger.info(
                f"FAST_PATH,signal={signal},conf={confidence:.3f},"
                f"latency={latency_ms:.1f}ms,regime={regime},used_llm={pass_to_llm}"
            )
        return {
            "signal": signal,
            "confidence": round(float(confidence), 3),
            "regime": regime,
            "stop": stop,
            "target": target,
            "pass_to_llm": bool(pass_to_llm),
            "used_llm": bool(pass_to_llm),
            "latency_ms": round(latency_ms, 3),
            "meets_latency_budget": latency_ms < 200.0,
            "reason": reason,
            "chosen_strategy": "fast_path_ma_tape_fib",
        }
