"""Causal MARK_EYES V2. Close-to-close only. Two extra slots after V1 three."""

from __future__ import annotations

from typing import Any

import numpy as np

from lumina_core.birth.awakening_mark_eyes import HOLD_NORM
from lumina_core.birth.awakening_mark_eyes_obs import close_to_close_unreal_r, unreal_r_from_rl
from lumina_core.birth.awakening_mark_eyes_v2 import (
    MARK_EYES_V2_EXTRA,
    MARK_EYES_V2_OBS_DIM,
    MarkEyesV2ProtocolError,
)
from lumina_core.rl.observation_builder import OBSERVATION_DIM

_ = close_to_close_unreal_r


class MarkEyesV2State:
    """Causal mark-path V2. Close-to-close only. No paper high/low wick."""

    unreal_r: float = 0.0
    mae_r: float = 0.0
    mfe_r: float = 0.0
    prev_unreal: float = 0.0
    d_unreal: float = 0.0
    bars_held: int = 0
    in_pos: bool = False
    _u_missing: bool = False

    def on_flat(self) -> None:
        self.unreal_r = 0.0
        self.mae_r = 0.0
        self.mfe_r = 0.0
        self.prev_unreal = 0.0
        self.d_unreal = 0.0
        self.bars_held = 0
        self.in_pos = False
        self._u_missing = False

    def on_step(self, position: int, unreal_r: float | None) -> None:
        if int(position) == 0:
            self.on_flat()
            return
        self.in_pos = True
        self.bars_held = int(self.bars_held) + 1
        if unreal_r is None:
            self._u_missing = True
            return
        self._u_missing = False
        u = float(unreal_r)
        if self.bars_held <= 1:
            self.mae_r = u
            self.mfe_r = u  # mfe is max unreal, not wick
            self.d_unreal = 0.0  # first in-position bar
            self.prev_unreal = u
        else:
            self.mae_r = float(min(self.mae_r, u))
            self.mfe_r = float(max(self.mfe_r, u))  # mfe is max unreal, not wick
            self.d_unreal = float(u - self.prev_unreal)
            self.prev_unreal = u
        self.unreal_r = u

    def extra_vec(self) -> tuple[float, float, float, float, float]:
        if not self.in_pos:
            return (0.0, 0.0, 0.0, 0.0, 0.0)
        bars_norm = float(min(float(self.bars_held) / HOLD_NORM, 1.0))
        if self._u_missing:
            return (0.0, 0.0, bars_norm, 0.0, 0.0)
        return (
            float(self.unreal_r),
            float(self.mae_r),
            bars_norm,
            float(self.mfe_r),
            float(self.d_unreal),
        )


def concat_mark_eyes_v2(base_obs: Any, extra: tuple[float, ...]) -> np.ndarray:
    """base_obs length MUST be OBSERVATION_DIM (43). Extra length 5. Result 48."""
    arr = np.asarray(base_obs, dtype=np.float32).reshape(-1)
    if int(arr.shape[0]) != int(OBSERVATION_DIM):
        raise MarkEyesV2ProtocolError(
            f"concat_mark_eyes_v2 requires len(base)=={OBSERVATION_DIM}, got {arr.shape[0]}"
        )
    extra_a = np.asarray(extra, dtype=np.float32).reshape(-1)
    if int(extra_a.shape[0]) != int(MARK_EYES_V2_EXTRA):
        raise MarkEyesV2ProtocolError(f"extra must have {MARK_EYES_V2_EXTRA} slots")
    out = np.concatenate([arr, extra_a]).astype(np.float32)
    if int(out.shape[0]) != int(MARK_EYES_V2_OBS_DIM):
        raise MarkEyesV2ProtocolError(f"concat result must be {MARK_EYES_V2_OBS_DIM}")
    return out


__all__ = [
    "MarkEyesV2State",
    "concat_mark_eyes_v2",
    "unreal_r_from_rl",
]
