"""Small action helpers extracted from sim_runner (M5 residual)."""

from __future__ import annotations

from typing import Any

import numpy as np

from lumina_core.birth.birth_trade_geometry import (
    BIRTH_FALLBACK_STOP_PCT,
    BIRTH_FALLBACK_TARGET_PCT,
    BirthTradeGeometry,
    geometry_action,
)

_DEFAULT_ACTION = np.array(
    [0.0, 0.5, BIRTH_FALLBACK_STOP_PCT, BIRTH_FALLBACK_TARGET_PCT], dtype=np.float32
)


def predict_actions(
    policy: Any, obs_batch: np.ndarray, *, deterministic: bool = True
) -> np.ndarray:
    """Batched policy forward. Shape (n, obs) → (n, action). One GPU call."""
    batch = np.asarray(obs_batch, dtype=np.float32)
    if batch.ndim == 1:
        batch = batch.reshape(1, -1)
    n = int(batch.shape[0])
    if policy is None:
        return np.tile(_DEFAULT_ACTION, (n, 1))
    predict = getattr(policy, "predict", None)
    if not callable(predict):
        return np.tile(_DEFAULT_ACTION, (n, 1))
    try:
        raw = predict(batch, deterministic=bool(deterministic))
        action = raw[0] if isinstance(raw, (tuple, list)) and len(raw) >= 1 else raw
        arr = np.asarray(action, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[0] == 1 and n > 1:
            arr = np.repeat(arr, n, axis=0)
        if arr.shape[0] != n:
            return np.tile(_DEFAULT_ACTION, (n, 1))
        return arr
    except Exception:
        return np.tile(_DEFAULT_ACTION, (n, 1))


def predict_action(
    policy: Any, obs: np.ndarray, *, deterministic: bool = True
) -> np.ndarray:
    vec = predict_actions(
        policy,
        np.asarray(obs, dtype=np.float32).reshape(1, -1),
        deterministic=deterministic,
    )
    return np.asarray(vec[0], dtype=np.float32).reshape(-1)


def exploration_action(
    exploration_step: int,
    geometry: BirthTradeGeometry | None = None,
) -> np.ndarray:
    side = 1.0 if exploration_step % 2 == 0 else 2.0
    geo = geometry or BirthTradeGeometry(
        stop_pct=BIRTH_FALLBACK_STOP_PCT,
        target_pct=BIRTH_FALLBACK_TARGET_PCT,
        source="fallback",
    )
    return geometry_action(side, 0.5, geo)


def hold_ratio(hold_signals: int, total_signals: int) -> float:
    return float(hold_signals) / float(max(1, total_signals))


__all__ = ["exploration_action", "hold_ratio", "predict_action", "predict_actions"]
