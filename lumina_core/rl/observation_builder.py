"""43-dim RL observation vector SSOT (ADR-0015 + ADR-0018).

Slot map:
  0   price
  1   trend_regime_strength (signed continuous, replaces binary regime_val)
  2-5 tape (volume_delta, avg_volume_delta_10, bid_ask_imbalance, cumulative_delta_10)
  6-9 dream (confidence, confluence, stop, target)
  10-12 fib (0.382, 0.5, 0.618)
  13-15 macro (vix, yield10y, dxy)
  16-21 position state (position, qty, entry_price, equity, drawdown, rolling_sharpe)
  22-23 step context (idx, len(data))
  24-27 bible (confluence, news, session, mtf)
  28-31 dna embedding (4 dims)
  32-34 trend ADX (7, 14, 21) normalized /100
  35-38 trend OLS slopes (5, 15, 30, 60 bars)
  39    trend_direction (-1, 0, +1)
  40    trend_duration_norm
  41    trend_atr_norm (ATR/price)
  42    trend_atr_ratio (ATR vs rolling mean, clipped)
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pandas as pd

from lumina_core.engine.analysis_helpers import has_ohlc_columns, normalize_ohlc_frame
from lumina_core.rl.trend_features import (
    MIN_TREND_LOOKBACK,
    compute_trend_features_from_ticks,
)

OBSERVATION_DIM = 43

_TREND_TAIL_KEYS = (
    "trend_adx_7",
    "trend_adx_14",
    "trend_adx_21",
    "trend_slope_5",
    "trend_slope_15",
    "trend_slope_30",
    "trend_slope_60",
    "trend_direction",
    "trend_duration_norm",
    "trend_atr_norm",
    "trend_atr_ratio",
)

_REGIME_MAP = {
    "TRENDING": 1.0,
    "TREND": 1.0,
    "BREAKOUT": 0.8,
    "RANGING": -0.6,
    "VOLATILE": -0.9,
    "NEUTRAL": 0.0,
    "SYNTHETIC": 0.0,
}


def regime_scalar(regime: str) -> float:
    upper = str(regime or "NEUTRAL").strip().upper()
    for key, val in _REGIME_MAP.items():
        if key in upper:
            return val
    return 0.0


def dna_embedding(dna_hash: str) -> list[float]:
    if not dna_hash:
        return [0.0, 0.0, 0.0, 0.0]
    raw = hashlib.sha256(dna_hash.encode("utf-8")).digest()
    return [(b / 127.5) - 1.0 for b in raw[:4]]


def _has_trend_features(row: dict[str, Any]) -> bool:
    return "trend_regime_strength" in row


def _trend_features_from_row_or_window(
    row: dict[str, Any],
    data: list[dict[str, Any]],
    idx: int,
) -> tuple[float, list[float]]:
    if _has_trend_features(row):
        strength = float(row.get("trend_regime_strength", 0.0) or 0.0)
        tail = [float(row.get(key, 0.0) or 0.0) for key in _TREND_TAIL_KEYS]
        return strength, tail

    window = data[max(0, idx - MIN_TREND_LOOKBACK) : idx + 1]
    computed = compute_trend_features_from_ticks(window)
    strength = float(computed.get("trend_regime_strength", 0.0) or 0.0)
    tail = [float(computed.get(key, 0.0) or 0.0) for key in _TREND_TAIL_KEYS]
    return strength, tail


def build_observation_vector(
    *,
    row: dict[str, Any],
    engine: Any,
    data: list[dict[str, Any]],
    idx: int,
    position: int,
    qty: int,
    entry_price: float,
    equity: float,
    drawdown: float,
    rolling_sharpe: float,
    dna_hash: str = "",
    trade_mode: str = "sim",
) -> np.ndarray:
    price = float(row.get("close", row.get("last", 0.0)) or 0.0)

    recent = data[max(0, idx - 120) : idx + 1]
    regime = str(row.get("regime", "NEUTRAL"))
    skip_regime_detection = trade_mode == "birth" and bool(str(row.get("regime", "")).strip())
    if not skip_regime_detection and len(recent) > 20 and hasattr(engine, "detect_market_regime"):
        try:
            frame = normalize_ohlc_frame(pd.DataFrame(recent))
            if has_ohlc_columns(frame):
                regime = str(engine.detect_market_regime(frame))
        except Exception:
            pass

    regime_strength, trend_tail = _trend_features_from_row_or_window(row, data, idx)
    if not _has_trend_features(row) and regime_strength == 0.0 and regime:
        regime_strength = regime_scalar(regime)

    tape = engine.market_data.get_tape_snapshot() if hasattr(engine, "market_data") else {}
    tape = tape if isinstance(tape, dict) else {}
    dream = engine.get_current_dream_snapshot() if hasattr(engine, "get_current_dream_snapshot") else {}
    dream = dream if isinstance(dream, dict) else {}
    fib_levels = dream.get("fib_levels") or getattr(engine, "AI_DRAWN_FIBS", {}) or {}
    world_model = getattr(engine, "world_model", {}) or {}
    macro = world_model.get("macro", {}) if isinstance(world_model, dict) else {}

    fib_0382 = float(fib_levels.get("0.382", price)) if isinstance(fib_levels, dict) else price
    fib_05 = float(fib_levels.get("0.5", price)) if isinstance(fib_levels, dict) else price
    fib_0618 = float(fib_levels.get("0.618", price)) if isinstance(fib_levels, dict) else price

    bible_confluence = float(row.get("bible_confluence", dream.get("confluence_score", 0.55) or 0.55))
    bible_news = float(row.get("bible_news_proximity", 1.0) or 1.0)
    bible_session = float(row.get("bible_session_phase", 0.0) or 0.0)
    bible_mtf = float(row.get("bible_mtf_bias", 0.0) or 0.0)

    return np.array(
        [
            price,
            regime_strength,
            float(tape.get("volume_delta", 0.0)),
            float(tape.get("avg_volume_delta_10", 0.0)),
            float(tape.get("bid_ask_imbalance", 1.0)),
            float(tape.get("cumulative_delta_10", 0.0)),
            float(dream.get("confidence", bible_confluence)),
            float(dream.get("confluence_score", bible_confluence)),
            float(dream.get("stop", 0.0)),
            float(dream.get("target", 0.0)),
            fib_0382,
            fib_05,
            fib_0618,
            float(macro.get("vix", 0.0)),
            float(macro.get("yield10y", 0.0)),
            float(macro.get("dxy", 0.0)),
            float(position),
            float(qty),
            float(entry_price),
            float(equity),
            float(drawdown),
            float(rolling_sharpe),
            float(idx),
            float(len(data)),
            bible_confluence,
            bible_news,
            bible_session,
            bible_mtf,
            *dna_embedding(dna_hash),
            *trend_tail,
        ],
        dtype=np.float32,
    )
