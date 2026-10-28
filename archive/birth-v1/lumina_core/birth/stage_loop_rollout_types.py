"""Rollout pre shared types (M5)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class RolloutPreState:
    explore_steps: int
    reward_override: Any
    hold_cap: float | None
    position_flat_cap: float | None
    position_flat_floor: float | None
    range_patience_active: bool
    plateau_recovery: bool
    progress_cb: Callable[..., None]
    participation_envelope_enabled: bool = False
    participation_min_signals: int = 50
    participation_min_dwell_bars: int = 8
    participation_band_lo: float = 0.30
    participation_band_hi: float = 0.70
    participation_hysteresis: float = 0.02
    participation_under_band_release_hysteresis: float = 0.02
    participation_stop_pct: float = 0.0012
    participation_target_pct: float = 0.0020
    participation_qty_frac: float = 0.15
    occupancy_control_window_bars: int = 500
    stage_range_flat_bars: int = 0
    stage_range_total_signals: int = 0
    expectancy_gap: float = 0.0
    stage2_expectancy_floor: float = -0.15
