"""28-dim observation vectors aligned with ``RLTradingEnvironment`` for birth SIM inference."""

from __future__ import annotations

from typing import Any

import numpy as np

BIRTH_RL_OBS_DIM = 28

_REGIME_MAP = {
    "TRENDING": 1.0,
    "TREND": 1.0,
    "BREAKOUT": 0.8,
    "RANGING": -0.6,
    "VOLATILE": -0.9,
    "NEUTRAL": 0.0,
    "SYNTHETIC": 0.0,
}


def _regime_value(regime: str) -> float:
    upper = str(regime or "NEUTRAL").strip().upper()
    for key, val in _REGIME_MAP.items():
        if key in upper:
            return val
    return 0.0


def _position_side_scalar(side: str) -> float:
    normalized = str(side or "NONE").strip().upper()
    if normalized == "BUY":
        return 1.0
    if normalized == "SELL":
        return -1.0
    return 0.0


def _rolling_sharpe_from_pnl(recent_pnl: list[float]) -> float:
    if len(recent_pnl) < 5:
        return 0.0
    arr = np.asarray(recent_pnl[-100:], dtype=np.float32)
    std = float(arr.std())
    if std <= 1e-8:
        return 0.0
    return float((arr.mean() / std) * np.sqrt(252.0))


def _drawdown_from_pnl(recent_pnl: list[float], *, equity: float) -> float:
    if not recent_pnl:
        return 0.0
    curve = [float(equity)]
    for pnl in recent_pnl[-200:]:
        curve.append(curve[-1] + float(pnl))
    peak = max(curve) if curve else equity
    if peak <= 0.0:
        return 0.0
    return max(0.0, (peak - curve[-1]) / peak)


def build_birth_rl_observation_vector(
    *,
    tick: dict[str, Any],
    position: dict[str, Any] | None,
    tick_index: int,
    tick_count: int,
    equity: float = 50_000.0,
    recent_pnl: list[float] | None = None,
) -> np.ndarray:
    """Build observation compatible with ``RLTradingEnvironment.observation_space`` (28,)."""
    price = float(tick.get("last", 0.0) or tick.get("close", 0.0) or 0.0)
    imbalance = float(tick.get("imbalance", 1.0) or 1.0)
    volume = float(tick.get("volume", 1) or 1)
    pnl_tail = list(recent_pnl or [])

    pos_side = 0.0
    pos_qty = 0.0
    entry_price = 0.0
    if position is not None:
        pos_side = _position_side_scalar(str(position.get("side", "NONE")))
        pos_qty = float(max(0, int(position.get("qty", 1) or 1)))
        entry_price = float(position.get("entry_price", 0.0) or 0.0)

    regime_val = _regime_value(str(tick.get("regime", "NEUTRAL")))
    # dream / fib / macro placeholders use price-neutral defaults for birth SIM
    obs = np.array(
        [
            price,
            regime_val,
            volume * imbalance * 0.01,
            volume * 0.01,
            imbalance,
            imbalance * volume * 0.001,
            0.0,
            0.0,
            float(position.get("stop", price) if position else 0.0),
            float(position.get("target", price) if position else 0.0),
            price,
            price,
            price,
            0.0,
            0.0,
            0.0,
            pos_side,
            pos_qty,
            entry_price,
            float(equity),
            _drawdown_from_pnl(pnl_tail, equity=equity),
            _rolling_sharpe_from_pnl(pnl_tail),
            float(max(0, tick_index)),
            float(max(1, tick_count)),
            0.0,
            0.0,
            0.0,
            0.0,
        ],
        dtype=np.float32,
    )
    if obs.shape[0] != BIRTH_RL_OBS_DIM:
        padded = np.zeros(BIRTH_RL_OBS_DIM, dtype=np.float32)
        padded[: min(BIRTH_RL_OBS_DIM, obs.shape[0])] = obs[: min(BIRTH_RL_OBS_DIM, obs.shape[0])]
        return padded
    return obs
