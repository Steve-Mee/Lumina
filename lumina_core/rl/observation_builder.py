"""32-dim RL observation vector SSOT (ADR-0015)."""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

OBSERVATION_DIM = 32

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
) -> np.ndarray:
    price = float(row.get("close", row.get("last", 0.0)) or 0.0)

    recent = data[max(0, idx - 120) : idx + 1]
    regime = str(row.get("regime", "NEUTRAL"))
    if len(recent) > 20 and hasattr(engine, "detect_market_regime"):
        try:
            regime = str(engine.detect_market_regime(__import__("pandas").DataFrame(recent)))
        except Exception:
            pass
    regime_val = regime_scalar(regime)

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
            regime_val,
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
        ],
        dtype=np.float32,
    )
