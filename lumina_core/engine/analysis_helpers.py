from __future__ import annotations

import asyncio
import json
from typing import Any

import pandas as pd


def detect_candle_patterns(df: pd.DataFrame, tf: str = "1min") -> dict[str, str]:
    if len(df) < 3:
        return {"pattern": "unknown", "description": "te weinig data"}

    last3 = df.iloc[-3:]
    prev = last3.iloc[-2]
    curr = last3.iloc[-1]

    body = abs(curr["close"] - curr["open"])
    upper_wick = curr["high"] - max(curr["open"], curr["close"])
    lower_wick = min(curr["open"], curr["close"]) - curr["low"]
    range_size = curr["high"] - curr["low"]

    patterns: dict[str, str] = {}

    if curr["close"] > prev["high"] and curr["open"] < prev["low"] and curr["close"] > curr["open"]:
        patterns["engulfing"] = "bullish_engulfing"
    elif curr["close"] < prev["low"] and curr["open"] > prev["high"] and curr["close"] < curr["open"]:
        patterns["engulfing"] = "bearish_engulfing"

    if lower_wick > 2 * body and upper_wick < body * 0.5 and curr["close"] > curr["open"]:
        patterns["pinbar"] = "hammer"
    elif upper_wick > 2 * body and lower_wick < body * 0.5 and curr["close"] < curr["open"]:
        patterns["pinbar"] = "shooting_star"

    if body <= range_size * 0.1:
        patterns["doji"] = "doji"

    if curr["high"] < prev["high"] and curr["low"] > prev["low"]:
        patterns["inside"] = "inside_bar"

    if patterns:
        main = list(patterns.values())[0]
        return {"pattern": main, "description": f"{tf} {main.replace('_', ' ')}"}
    return {"pattern": "none", "description": "geen duidelijk patroon"}


def generate_price_action_summary(df: pd.DataFrame, timeframes: dict[str, int]) -> str:
    if len(df) < 120:
        return "INSUFFICIENT_DATA"

    summary_parts: list[str] = []
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    for tf_name, seconds in list(timeframes.items())[:4]:
        res = (
            df.set_index("timestamp")
            .resample(f"{seconds // 60}min")
            .agg({"high": "max", "low": "min"})
            .dropna()
            .iloc[-3:]
        )
        if len(res) >= 2:
            prev_h, curr_h = res["high"].iloc[-2], res["high"].iloc[-1]
            prev_l, curr_l = res["low"].iloc[-2], res["low"].iloc[-1]
            if curr_h > prev_h and curr_l > prev_l:
                summary_parts.append(f"Higher High + Higher Low op {tf_name}")
            elif curr_h < prev_h and curr_l < prev_l:
                summary_parts.append(f"Lower High + Lower Low op {tf_name}")

    recent_vol = float(df["volume"].iloc[-20:].mean())
    last_vol = float(df["volume"].iloc[-1])
    if recent_vol > 0 and last_vol > recent_vol * 2.5:
        summary_parts.append(f"Volume spike {last_vol / recent_vol:.1f}x gemiddeld")

    df_5 = df.set_index("timestamp").resample("5min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    df_15 = df.set_index("timestamp").resample("15min").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()

    pat5 = detect_candle_patterns(df_5, "5min")
    pat15 = detect_candle_patterns(df_15, "15min")
    if pat5["pattern"] != "none":
        summary_parts.append(pat5["description"])
    if pat15["pattern"] != "none":
        summary_parts.append(pat15["description"])

    current_price = float(df["close"].iloc[-1])
    ma20 = float(df["close"].rolling(20).mean().iloc[-1])
    bias = "BULLISH" if current_price > ma20 else "BEARISH"
    summary_parts.append(f"Overall bias: {bias} (prijs vs 20-period MA)")

    return " | ".join(summary_parts) if summary_parts else "NEUTRALE MARKT – geen duidelijke price action"


def detect_market_regime(df: pd.DataFrame) -> str:
    if len(df) < 60:
        return "UNKNOWN"

    close = df["close"]
    high = df["high"]
    low = df["low"]
    vol = df["volume"]

    tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    up = (high - high.shift()).clip(lower=0)
    down = (low.shift() - low).clip(lower=0)
    plus_di = 100 * (up.ewm(alpha=1 / 14).mean() / atr)
    minus_di = 100 * (down.ewm(alpha=1 / 14).mean() / atr)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = float(dx.rolling(14).mean().iloc[-1])

    avg_range = float((high - low).rolling(20).mean().iloc[-1])
    recent_range = float((high.iloc[-20:] - low.iloc[-20:]).mean())
    vol_spike = bool(vol.iloc[-1] > vol.rolling(20).mean().iloc[-1] * 2.0)

    if adx > 25 and recent_range > avg_range * 1.3:
        return "TRENDING"
    if adx < 20 and recent_range < avg_range * 0.7:
        return "RANGING"
    if vol_spike and recent_range > avg_range * 1.8:
        return "VOLATILE"
    if abs(float(close.iloc[-1]) - float(close.iloc[-20])) > avg_range * 3:
        return "BREAKOUT"
    return "NEUTRAL"


def detect_market_structure(df: pd.DataFrame) -> dict[str, Any]:
    if len(df) < 50:
        return {"bos": None, "choch": None, "order_blocks": [], "fvg": []}

    recent = df.iloc[-40:].reset_index(drop=True)
    highs = recent["high"]
    lows = recent["low"]

    structure: dict[str, Any] = {"bos": None, "choch": None, "order_blocks": [], "fvg": []}

    last_swing_high = highs.iloc[-10:-1].max()
    last_swing_low = lows.iloc[-10:-1].min()
    current_high = highs.iloc[-1]
    current_low = lows.iloc[-1]

    if current_high > last_swing_high and current_low > last_swing_low:
        structure["bos"] = "bullish_BOS"
    elif current_high < last_swing_high and current_low < last_swing_low:
        structure["bos"] = "bearish_BOS"
    if (current_high < last_swing_high and current_low > last_swing_low) or (current_high > last_swing_high and current_low < last_swing_low):
        structure["choch"] = "CHOCH_detected"

    structure["order_blocks"] = [
        {"type": "bullish_OB", "price": float(lows.iloc[-15:-5].min())},
        {"type": "bearish_OB", "price": float(highs.iloc[-15:-5].max())},
    ]

    if len(recent) >= 3:
        c1_high = recent["high"].iloc[-3]
        c3_low = recent["low"].iloc[-1]
        if c3_low > c1_high:
            structure["fvg"].append({"type": "bullish_FVG", "price": float((c1_high + c3_low) / 2)})
        c1_low = recent["low"].iloc[-3]
        c3_high = recent["high"].iloc[-1]
        if c1_low > c3_high:
            structure["fvg"].append({"type": "bearish_FVG", "price": float((c1_low + c3_high) / 2)})

    return structure


def calculate_dynamic_confluence(regime: str, recent_winrate: float) -> float:
    base = 0.70
    if regime == "TRENDING":
        base += 0.08
    elif regime == "RANGING":
        base -= 0.05
    elif regime == "VOLATILE":
        base += 0.03
    elif regime == "BREAKOUT":
        base += 0.12

    if recent_winrate > 0.65:
        base += 0.05
    elif recent_winrate < 0.45:
        base += 0.08

    return max(0.55, min(0.95, round(base, 2)))


def is_significant_event(current_price: float, previous_price: float, regime: str, event_threshold: float) -> bool:
    price_change = abs(current_price - previous_price) / previous_price if previous_price else 0.0
    return price_change > event_threshold or regime in ["TRENDING", "BREAKOUT", "VOLATILE"]


def update_cost_tracker_from_usage(cost_tracker: dict[str, Any], usage: dict[str, Any] | None, channel: str = "reasoning") -> None:
    if not usage:
        return

    tokens = usage.get("total_tokens")
    if tokens is None:
        tokens = (usage.get("prompt_tokens") or usage.get("input_tokens") or 0) + (usage.get("completion_tokens") or usage.get("output_tokens") or 0)

    try:
        token_count = int(tokens)
    except (TypeError, ValueError):
        return

    if channel == "vision":
        cost_tracker["vision_tokens"] = int(cost_tracker.get("vision_tokens", 0)) + token_count
        cost_tracker["today"] = float(cost_tracker.get("today", 0.0)) + (token_count / 1000.0) * 0.015
    else:
        cost_tracker["reasoning_tokens"] = int(cost_tracker.get("reasoning_tokens", 0)) + token_count
        cost_tracker["today"] = float(cost_tracker.get("today", 0.0)) + (token_count / 1000.0) * 0.007


def run_async_safely(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def parse_json_loose(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    return json.loads(text)


def build_pa_signature(pa_summary: str) -> str:
    return " ".join(str(pa_summary).lower().split())[:220]
