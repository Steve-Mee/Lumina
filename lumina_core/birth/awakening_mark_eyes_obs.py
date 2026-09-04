"""Causal mark-path eyes. Close-to-close only. No high/low wick."""

from __future__ import annotations

from typing import Any

import numpy as np

from lumina_core.birth.awakening_mark_eyes import (
    HOLD_NORM,
    MARK_EYES_EXTRA,
    MARK_EYES_OBS_DIM,
    MarkEyesProtocolError,
)
from lumina_core.rl.observation_builder import OBSERVATION_DIM


class MarkEyesState:
    """Causal mark-path. Close-to-close only. No high/low wick."""

    unreal_r: float = 0.0
    mae_r: float = 0.0
    bars_held: int = 0
    in_pos: bool = False

    def on_flat(self) -> None:
        self.unreal_r = 0.0
        self.mae_r = 0.0
        self.bars_held = 0
        self.in_pos = False

    def on_step(self, position: int, unreal_r: float | None) -> None:
        if int(position) == 0:
            self.on_flat()
            return
        self.in_pos = True
        self.bars_held = int(self.bars_held) + 1
        if unreal_r is None:
            return
        u = float(unreal_r)
        self.unreal_r = u
        if self.bars_held <= 1:
            self.mae_r = u
        else:
            self.mae_r = float(min(self.mae_r, u))

    def extra_vec(self) -> tuple[float, float, float]:
        if not self.in_pos:
            return (0.0, 0.0, 0.0)
        return (
            float(self.unreal_r),
            float(self.mae_r),
            float(min(float(self.bars_held) / HOLD_NORM, 1.0)),
        )


def close_to_close_unreal_r(
    *,
    position: int,
    entry_price: float,
    mark: float | None,
    stop_pct: float | None,
    point_value: float,
) -> float | None:
    """Same dollar→R conversion as path-exit intended risk. Fail-closed to None."""
    if int(position) == 0:
        return None
    if mark is None:
        return None
    try:
        entry = float(entry_price)
        stop = float(stop_pct) if stop_pct is not None else 0.0
        px = float(mark)
        pv = float(point_value)
    except (TypeError, ValueError):
        return None
    if entry <= 0.0 or stop <= 0.0 or pv <= 0.0:
        return None
    from lumina_core.birth.foundation_metrics import intended_risk_usd

    denom = float(intended_risk_usd(stop_pct=stop, entry_price=entry, qty=1, point_value=pv))
    if denom <= 0.0:
        return None
    usd = (px - entry) * float(position) * pv
    return float(usd) / float(denom)


def unreal_r_from_rl(rl: Any) -> float | None:
    pos = int(getattr(rl, "_position", 0) or 0)
    if pos == 0:
        return None
    data = getattr(rl, "data", None) or []
    try:
        idx = int(getattr(rl, "_idx", 0) or 0)
        row = data[min(idx, len(data) - 1)] if data else None
    except (TypeError, ValueError, IndexError):
        row = None
    mark_raw = None
    if isinstance(row, dict):
        mark_raw = row.get("close", row.get("last"))
    try:
        mark = float(mark_raw) if mark_raw is not None else None
    except (TypeError, ValueError):
        mark = None
    from lumina_core.birth.notional_cap import birth_gym_point_value

    return close_to_close_unreal_r(
        position=pos,
        entry_price=float(getattr(rl, "_entry_price", 0.0) or 0.0),
        mark=mark,
        stop_pct=float(getattr(rl, "_entry_stop_pct", 0.0) or 0.0),
        point_value=float(birth_gym_point_value()),
    )


def concat_mark_eyes(
    base_obs: Any,
    extra: tuple[float, float, float],
) -> np.ndarray:
    """base_obs length MUST be OBSERVATION_DIM (43). Result length 46."""
    arr = np.asarray(base_obs, dtype=np.float32).reshape(-1)
    if int(arr.shape[0]) != int(OBSERVATION_DIM):
        raise MarkEyesProtocolError(
            f"concat_mark_eyes requires len(base)=={OBSERVATION_DIM}, got {arr.shape[0]}"
        )
    extra_a = np.asarray(extra, dtype=np.float32).reshape(-1)
    if int(extra_a.shape[0]) != int(MARK_EYES_EXTRA):
        raise MarkEyesProtocolError(f"extra must have {MARK_EYES_EXTRA} slots")
    out = np.concatenate([arr, extra_a]).astype(np.float32)
    if int(out.shape[0]) != int(MARK_EYES_OBS_DIM):
        raise MarkEyesProtocolError(f"concat result must be {MARK_EYES_OBS_DIM}")
    return out


__all__ = [
    "MarkEyesState",
    "close_to_close_unreal_r",
    "concat_mark_eyes",
    "unreal_r_from_rl",
]
