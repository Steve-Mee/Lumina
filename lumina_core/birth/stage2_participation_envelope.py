"""Stage-2 Participation Envelope — hard occupancy physics for flat band.

``position_flat`` is bar-level occupancy (fraction of range bars with position==0).
Soft explore/reward cannot move a 95%+ flat ratio: opens die in 1–few bars.

This module is curriculum law (like risk clip): when occupancy is outside the
30–70% pass band, the SIM runner applies deterministic overrides so the metric
can recover. Birth SIM only; stops stay ≤1%.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ParticipationMode = Literal["PASSTHROUGH", "FORCE_OPEN", "FORCE_HOLD", "FORCE_FLAT"]

MODE_PASSTHROUGH: ParticipationMode = "PASSTHROUGH"
MODE_FORCE_OPEN: ParticipationMode = "FORCE_OPEN"
MODE_FORCE_HOLD: ParticipationMode = "FORCE_HOLD"
MODE_FORCE_FLAT: ParticipationMode = "FORCE_FLAT"


@dataclass(frozen=True, slots=True)
class ParticipationDecision:
    mode: ParticipationMode
    """Action override as [side, qty_frac, stop_pct, target_pct] or None."""
    action_override: tuple[float, float, float, float] | None
    reason: str
    suppress_flatten: bool = False


def decide_stage2_participation(
    *,
    enabled: bool,
    range_flat_ratio: float,
    range_total_signals: int,
    position: int,
    bars_in_position: int,
    force_open_step: int = 0,
    min_signals: int = 50,
    min_dwell_bars: int = 8,
    band_lo: float = 0.30,
    band_hi: float = 0.70,
    # Hysteresis: force only outside enter thresholds; pass inside band core.
    # Prevents thrash at exact 0.30/0.70 when expectancy quality learning needs
    # selective entries near the pass band.
    hysteresis: float = 0.02,
    stop_pct: float = 0.0075,
    target_pct: float = 0.015,
    qty_frac: float = 0.15,
) -> ParticipationDecision:
    """Return participation mode for one SIM step.

    FORCE_OPEN: flat empty and over-flat band → micro-entry (constitution-safe stops).
    FORCE_HOLD: in position under min dwell while over-flat → hold open (no flatten).
    FORCE_FLAT: under-flat band → suppress new entries.
    PASSTHROUGH: in band or warm-up.
    """
    if not enabled:
        return ParticipationDecision(MODE_PASSTHROUGH, None, "disabled")

    signals = int(range_total_signals)
    if signals < max(1, int(min_signals)):
        return ParticipationDecision(MODE_PASSTHROUGH, None, "warmup_signals")

    flat = float(range_flat_ratio)
    lo = float(band_lo)
    hi = float(band_hi)
    if lo >= hi:
        lo, hi = 0.30, 0.70
    hyst = max(0.0, min(0.08, float(hysteresis)))
    # Force-open only when clearly over-flat; force-flat only when clearly under-flat.
    force_open_hi = hi + hyst  # e.g. 0.72
    force_flat_lo = lo - hyst  # e.g. 0.28

    pos = int(position)
    dwell = max(0, int(bars_in_position))
    min_dwell = max(1, int(min_dwell_bars))
    stop = max(0.001, min(0.01, float(stop_pct)))
    target = max(stop, min(0.05, float(target_pct)))
    q = max(0.0, min(1.0, float(qty_frac)))

    # Over-flat: need more time in market (hysteresis avoids thrash at 70%).
    if flat > force_open_hi + 1e-12:
        if pos == 0:
            # Alternate long/short for balanced force opens.
            side = 1.0 if (int(force_open_step) % 2 == 0) else 2.0
            return ParticipationDecision(
                MODE_FORCE_OPEN,
                (side, q, stop, target),
                "over_flat_force_open",
                suppress_flatten=True,
            )
        if dwell < min_dwell:
            # Hold action while keeping position; gym must not random-flatten.
            return ParticipationDecision(
                MODE_FORCE_HOLD,
                (0.0, 0.5, stop, target),
                "over_flat_min_dwell",
                suppress_flatten=True,
            )
        # Dwell satisfied: allow policy to manage; still suppress random flatten.
        return ParticipationDecision(
            MODE_PASSTHROUGH,
            None,
            "over_flat_dwell_ok_passthrough",
            suppress_flatten=True,
        )

    # Soft over-flat (hi < flat <= force_open_hi): hold protect only, no new force open.
    if flat > hi + 1e-12 and pos != 0 and dwell < min_dwell:
        return ParticipationDecision(
            MODE_FORCE_HOLD,
            (0.0, 0.5, stop, target),
            "over_flat_soft_min_dwell",
            suppress_flatten=True,
        )

    # Under-flat: over-trading — suppress new entries only past hysteresis.
    if flat < force_flat_lo - 1e-12:
        if pos == 0:
            return ParticipationDecision(
                MODE_FORCE_FLAT,
                (0.0, 0.5, stop, target),
                "under_flat_suppress_entry",
                suppress_flatten=False,
            )
        return ParticipationDecision(
            MODE_PASSTHROUGH,
            None,
            "under_flat_manage_exit",
            suppress_flatten=False,
        )

    return ParticipationDecision(MODE_PASSTHROUGH, None, "in_band")


def participation_telemetry(counts: dict[str, int]) -> dict[str, int]:
    """Normalize counter dict for progress SSOT."""
    return {
        "participation_force_open": int(counts.get(MODE_FORCE_OPEN, 0) or 0),
        "participation_force_hold": int(counts.get(MODE_FORCE_HOLD, 0) or 0),
        "participation_force_flat": int(counts.get(MODE_FORCE_FLAT, 0) or 0),
        "participation_passthrough": int(counts.get(MODE_PASSTHROUGH, 0) or 0),
        "participation_overrides_total": int(
            (counts.get(MODE_FORCE_OPEN, 0) or 0)
            + (counts.get(MODE_FORCE_HOLD, 0) or 0)
            + (counts.get(MODE_FORCE_FLAT, 0) or 0)
        ),
    }


__all__ = [
    "MODE_FORCE_FLAT",
    "MODE_FORCE_HOLD",
    "MODE_FORCE_OPEN",
    "MODE_PASSTHROUGH",
    "ParticipationDecision",
    "ParticipationMode",
    "decide_stage2_participation",
    "participation_telemetry",
]
