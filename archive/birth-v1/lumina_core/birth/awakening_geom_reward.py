"""Train-only Awakening close reward. GEOM_WIN_R==1.21 GEOM_LOSS_R==-1.04."""

from __future__ import annotations

from typing import Literal

GEOM_WIN_R = 1.21  # GEOM_WIN_R==1.21
GEOM_LOSS_R = -1.04  # GEOM_LOSS_R==-1.04
USE_GEOM_CLOSE_REWARD = False
CloseKind = Literal["target", "stop", "time"]
TARGET_ALIASES = frozenset({"target", "geometry-win", "geometry_win", "win"})
STOP_ALIASES = frozenset({"stop", "geometry-loss", "geometry_loss", "loss"})


class GeomProtocolError(RuntimeError):
    """AWAKENING_GEOMETRY_REWARD protocol crime (fail-closed)."""


def map_close_reason(reason: str) -> CloseKind:
    text = str(reason or "").strip().lower()
    if text in TARGET_ALIASES:
        return "target"
    if text in STOP_ALIASES:
        return "stop"
    return "time"


def geom_close_reward(process_r: float, reason: str, regime: str) -> float:
    """Replace the close scalar only. Per-bar mark-to-market is unchanged."""
    del process_r, regime
    kind = map_close_reason(reason)
    if kind == "target":
        return float(GEOM_WIN_R)
    if kind == "stop":
        return float(GEOM_LOSS_R)
    return 0.0


assert GEOM_WIN_R == 1.21 and GEOM_LOSS_R == -1.04
assert USE_GEOM_CLOSE_REWARD is False

__all__ = [
    "GEOM_LOSS_R",
    "GEOM_WIN_R",
    "USE_GEOM_CLOSE_REWARD",
    "CloseKind",
    "GeomProtocolError",
    "geom_close_reward",
    "map_close_reason",
]
