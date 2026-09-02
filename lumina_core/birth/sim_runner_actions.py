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


def predict_action(
    policy: Any, obs: np.ndarray, *, deterministic: bool = True
) -> np.ndarray:
    if policy is None:
        return _DEFAULT_ACTION.copy()
    predict = getattr(policy, "predict", None)
    if not callable(predict):
        return _DEFAULT_ACTION.copy()
    try:
        raw = predict(obs, deterministic=bool(deterministic))
        if isinstance(raw, (tuple, list)) and len(raw) >= 1:
            action = raw[0]
        else:
            action = raw
        return np.asarray(action, dtype=np.float32).reshape(-1)
    except Exception:
        return _DEFAULT_ACTION.copy()


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


__all__ = ["exploration_action", "hold_ratio", "predict_action"]
