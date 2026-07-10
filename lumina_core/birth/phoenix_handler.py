"""PhoenixHandler — single responsibility for phoenix rebirth loops.

Logic lives in phoenix_loop.py. This module owns publishing of
birth.phoenix.cycle events when cycles are triggered.
"""

from __future__ import annotations

from lumina_core.birth.phoenix_loop import (
    PHOENIX_CYCLE_REASON,
    PhoenixLoopState,
    PhoenixNoveltyAction,
    can_start_phoenix,
    select_phoenix_novelty,
)

__all__ = [
    "PHOENIX_CYCLE_REASON",
    "PhoenixLoopState",
    "PhoenixNoveltyAction",
    "can_start_phoenix",
    "select_phoenix_novelty",
]
