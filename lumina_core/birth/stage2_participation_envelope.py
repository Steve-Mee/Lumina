"""Stage-2 Participation Envelope — hard occupancy physics for flat band.

``position_flat`` / ``range_flat_ratio`` = fraction of bars with **position==0**
(empty). Physics polarity (do not invert):

- **High flat** (> band_hi): under-activity → FORCE_OPEN / FORCE_HOLD
- **Low flat** (< band_lo): over-trading → FORCE_FLAT (suppress new entries)
  and optionally FORCE_EXIT after max dwell so zombie holds cannot pin flat < 30%.

Soft explore/reward cannot move a 95%+ flat ratio: opens die in 1–few bars.
This module is curriculum law (like risk clip). Birth SIM only; stops stay ≤1%.

The envelope is **airframe** — never disable it under quality lock / PPO freeze.
In-band PASSTHROUGH is the nominal law; under-band FORCE_FLAT stays on.

Control vs exam: pass-gate uses **cumulative** plant-flat in [0.30, 0.70]
for S2. Dual IMU (do not invert):

- Under-band (flat too low / over-trading): ``min(rolling, cumulative)``.
  A recent occupancy crash cannot hide behind a 28k-bar average.
- Over-band (flat too high / too empty): ``max(rolling, cumulative)``.
  A 500-bar in-band window cannot hide a 90% cumulative exam fail.
  Rolling-only over-flat lets FORCE_OPEN stop while the exam stays ~90%.
- In-band PASSTHROUGH when **both** IMUs are inside the band (after
  hysteresis / settle-corridor). Under-band still wins when both fire.

Live forensics 2026-08: hysteresis dead-zone left flat stuck at ~28% (pass needs
≥30%) while FORCE_FLAT only fired below 28%. Asymmetric law: **enter under-band
control at band_lo**. Empty-suppress **release** hysteresis default is **0.02**
so FORCE_FLAT holds until flat ≥ 0.32 (settle inside the exam, no 0.2996 chatter).

In-position FORCE_HOLD only when truly under exam (flat < 0.30). Once
``band_lo ≤ flat < release`` the exam is already in-band: PASSTHROUGH so the
envelope is not a 90% HOLD puppet at 0.319. Stage-3 keeps release hyst 0.0
(wider 25–75% exam). Floors unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ParticipationMode = Literal[
    "PASSTHROUGH",
    "FORCE_OPEN",
    "FORCE_HOLD",
    "FORCE_FLAT",
    "FORCE_EXIT",
]

MODE_PASSTHROUGH: ParticipationMode = "PASSTHROUGH"
MODE_FORCE_OPEN: ParticipationMode = "FORCE_OPEN"
MODE_FORCE_HOLD: ParticipationMode = "FORCE_HOLD"
MODE_FORCE_FLAT: ParticipationMode = "FORCE_FLAT"
MODE_FORCE_EXIT: ParticipationMode = "FORCE_EXIT"


@dataclass(frozen=True, slots=True)
class ParticipationDecision:
    mode: ParticipationMode
    """Action override as [side, qty_frac, stop_pct, target_pct] or None."""
    action_override: tuple[float, float, float, float] | None
    reason: str
    suppress_flatten: bool = False
    force_flatten: bool = False
    # Geometry time-stop: gym prefers stop/target if already hit, else mark PnL.
    force_time_stop: bool = False


def occupancy_control_flat(
    *,
    cumulative_flat: float,
    rolling_flat: float | None = None,
) -> float:
    """Under-band IMU: min(rolling, cumulative). Cumulative-only when rolling unknown."""
    cum = float(cumulative_flat)
    if rolling_flat is None:
        return cum
    return min(cum, float(rolling_flat))


def occupancy_control_over(
    *,
    cumulative_flat: float,
    rolling_flat: float | None = None,
) -> float:
    """Over-band IMU: max(rolling, cumulative). Cumulative-only when rolling unknown.

    Exam grades cumulative plant-flat. FORCE_OPEN must keep firing while the
    exam is still too empty, even if the short rolling window already looks
    in-band. Rolling-only over-flat lets cumulative stall at ~90%.
    """
    cum = float(cumulative_flat)
    if rolling_flat is None:
        return cum
    return max(cum, float(rolling_flat))


def force_open_stop_from_atr(
    *,
    atr_pct: float,
    min_dwell_bars: int = 8,
    min_stop_pct: float | None = None,
    max_stop_pct: float | None = None,
) -> float:
    """Widen FORCE_OPEN stop so a plant entry can survive min_dwell in expectation.

    Scale is tape ATR × sqrt(min_dwell) (random-walk bars). Still a live stop:
    ``hit_stop`` stays on. Clipped to constitution [min_stop, 1%].
    """
    try:
        from lumina_core.birth.birth_constitution_guard import (
            BIRTH_MAX_RISK_STOP_PCT,
            BIRTH_MIN_STOP_PCT,
        )

        stop_lo = float(BIRTH_MIN_STOP_PCT) if min_stop_pct is None else float(min_stop_pct)
        stop_hi = float(BIRTH_MAX_RISK_STOP_PCT) if max_stop_pct is None else float(max_stop_pct)
    except Exception:
        stop_lo = 0.0004 if min_stop_pct is None else float(min_stop_pct)
        stop_hi = 0.01 if max_stop_pct is None else float(max_stop_pct)
    if stop_lo > stop_hi:
        stop_lo, stop_hi = stop_hi, stop_lo
    atr = max(0.0, float(atr_pct))
    dwell = max(1, int(min_dwell_bars))
    raw = atr * (float(dwell) ** 0.5) if atr > 0.0 else stop_lo
    return max(stop_lo, min(stop_hi, raw))


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
    # Over-flat enter hysteresis only (under-flat uses asymmetric release below).
    hysteresis: float = 0.02,
    stop_pct: float = 0.0012,
    target_pct: float = 0.0020,
    qty_frac: float = 0.15,
    # Max bars in position while under-flat before FORCE_EXIT (geometry hold).
    max_hold_bars: int = 120,
    # After recovering into band, keep EMPTY suppress until flat ≥ band_lo + this.
    # Stage-2 default 0.02 settles 2pp inside the exam (kills the 0.2996 fencepost).
    # In-position FORCE_HOLD is NOT applied in that settle corridor (see body).
    under_band_release_hysteresis: float = 0.02,
    # Stage-2 expectancy gap (floor − live). Informational; in-band FORCE_EXIT is off by default.
    expectancy_gap: float = 0.0,
    # When True (default), FORCE_EXIT on sticky under-band (flat < release), not only deep_under.
    force_exit_on_sticky_under: bool = True,
    # In-band max-dwell FORCE_EXIT under exp gap. Default OFF: that path flatten-cut
    # winners (live forensics 2026-08-12: 6 flatten / 1 target). Occupancy exits stay
    # under-band only. Floors unchanged.
    force_exit_on_expectancy_gap: bool = False,
    # Rolling occupancy window (last N bars). None → cumulative-only (legacy tests).
    rolling_flat_ratio: float | None = None,
    # S3 application flag: exam grades cumulative occupancy. Once cumulative is
    # inside the controller band, PASSTHROUGH so rolling IMU cannot keep
    # FORCE_OPEN / FORCE_FLAT owning the book. S2 keeps dual-IMU (False).
    # Does not change band_lo / band_hi.
    cumulative_in_band_passthrough: bool = False,
) -> ParticipationDecision:
    """Return participation mode for one SIM step.

    FORCE_OPEN: over-flat (too empty) → micro-entry (constitution-safe stops).
    FORCE_HOLD: (a) over-flat min-dwell protect, or (b) true under-exam in
      position (flat < band_lo) so policy cannot reverse into more occupancy.
    FORCE_FLAT: under-flat or settle-corridor empty → suppress new entries.
    FORCE_EXIT: max-dwell occupancy exit (under-band / settle). Time-stop, not flatten.
    PASSTHROUGH: in band, or in-position once exam-in-band (flat ≥ band_lo) even
      if empty-suppress is still active until release (0.32). Policy manages the
      open trade; new entries stay blocked while empty.

    Under-band uses min(rolling, cumulative). Over-flat FORCE_OPEN uses
    max(rolling, cumulative) so a short in-band window cannot hide a high
    cumulative exam fail. Under-band wins when both fire.
    """
    if not enabled:
        return ParticipationDecision(MODE_PASSTHROUGH, None, "disabled")

    signals = int(range_total_signals)
    if signals < max(1, int(min_signals)):
        return ParticipationDecision(MODE_PASSTHROUGH, None, "warmup_signals")

    cum_flat = float(range_flat_ratio)
    roll_flat = float(rolling_flat_ratio) if rolling_flat_ratio is not None else None
    under_flat = occupancy_control_flat(
        cumulative_flat=cum_flat, rolling_flat=roll_flat
    )
    over_flat = occupancy_control_over(
        cumulative_flat=cum_flat, rolling_flat=roll_flat
    )
    lo = float(band_lo)
    hi = float(band_hi)
    if lo >= hi:
        lo, hi = 0.30, 0.70
    # S3: cumulative exam in-band owns PASSTHROUGH. Rolling 0.278 vs band_lo 0.28
    # must not FORCE_FLAT while exam occupancy is 0.57. Bands unchanged.
    if bool(cumulative_in_band_passthrough) and lo - 1e-12 <= cum_flat <= hi + 1e-12:
        return ParticipationDecision(MODE_PASSTHROUGH, None, "exam_cumulative_in_band")
    hyst = max(0.0, min(0.08, float(hysteresis)))
    release_hyst = max(0.0, min(0.08, float(under_band_release_hysteresis)))
    # Over-flat enter only clearly above band (hysteresis).
    force_open_hi = hi + hyst  # e.g. 0.72
    # Under-flat: ENTER empty-suppress as soon as flat < band_lo (no 28–30% dead
    # zone). RELEASE empty-suppress after flat clears band_lo + release_hyst
    # (Stage-2 0.32). In-position HOLD only below band_lo (exam), not in settle.
    under_band_enter = lo  # 0.30
    under_band_release = lo + release_hyst  # 0.32 when Stage-2 default hyst 0.02

    pos = int(position)
    dwell = max(0, int(bars_in_position))
    min_dwell = max(1, int(min_dwell_bars))
    max_hold = max(min_dwell + 1, int(max_hold_bars))
    exp_gap = max(0.0, float(expectancy_gap))
    try:
        from lumina_core.birth.birth_constitution_guard import (
            BIRTH_MAX_RISK_STOP_PCT,
            BIRTH_MIN_STOP_PCT,
        )

        _stop_lo = float(BIRTH_MIN_STOP_PCT)
        _stop_hi = float(BIRTH_MAX_RISK_STOP_PCT)
    except Exception:
        _stop_lo, _stop_hi = 0.0004, 0.01
    stop = max(_stop_lo, min(_stop_hi, float(stop_pct)))
    target = max(stop * 1.25, min(0.05, float(target_pct)))
    q = max(0.0, min(1.0, float(qty_frac)))

    def _force_exit(reason: str) -> ParticipationDecision:
        # Geometry time-stop: gym prefers stop/target if already hit, else mark
        # with honest net_pnl. Never force_flatten (that murdered first-touch WR).
        return ParticipationDecision(
            MODE_FORCE_EXIT,
            (0.0, 0.5, stop, target),
            reason,
            suppress_flatten=False,
            force_flatten=False,
            force_time_stop=True,
        )

    # Under-band first (occupancy exam + recent crash). Dual-signal: rolling 15%
    # with cumulative 35% must FORCE_FLAT — IMU, not T-0 average.
    if under_flat < under_band_release - 1e-12:
        deep_under = under_flat < under_band_enter - 1e-12
        sticky_exit = bool(force_exit_on_sticky_under) or deep_under
        if pos != 0 and dwell >= max_hold and sticky_exit:
            return _force_exit(
                "under_flat_max_dwell_exit_deep"
                if deep_under
                else "under_flat_max_dwell_exit_sticky"
            )
        if pos == 0:
            return ParticipationDecision(
                MODE_FORCE_FLAT,
                (0.0, 0.5, stop, target),
                (
                    "under_flat_suppress_entry"
                    if deep_under
                    else "under_flat_release_hyst_suppress"
                ),
                suppress_flatten=False,
            )
        # True under-exam: no reverse/add. Settle corridor (flat ≥ band_lo, still
        # < release): exam already in-band — PASSTHROUGH so 0.30–0.32 is not a
        # FORCE_HOLD puppet. Empty-suppress above still blocks the next entry.
        if deep_under:
            return ParticipationDecision(
                MODE_FORCE_HOLD,
                (0.0, 0.5, stop, target),
                "under_flat_manage_hold",
                suppress_flatten=False,
            )
        return ParticipationDecision(
            MODE_PASSTHROUGH,
            None,
            "under_flat_settle_in_exam_passthrough",
            suppress_flatten=False,
        )

    # Over-flat IMU is max(rolling, cumulative): exam-empty still FORCE_OPEN
    # even when the rolling window already looks in-band.
    if over_flat > force_open_hi + 1e-12:
        if pos == 0:
            side = 1.0 if (int(force_open_step) % 2 == 0) else 2.0
            return ParticipationDecision(
                MODE_FORCE_OPEN,
                (side, q, stop, target),
                "over_flat_force_open",
                suppress_flatten=True,
            )
        if dwell < min_dwell:
            return ParticipationDecision(
                MODE_FORCE_HOLD,
                (0.0, 0.5, stop, target),
                "over_flat_min_dwell",
                suppress_flatten=True,
            )
        return ParticipationDecision(
            MODE_PASSTHROUGH,
            None,
            "over_flat_dwell_ok_passthrough",
            suppress_flatten=True,
        )

    # Soft over-flat (hi < over_flat IMU <= force_open_hi): hold protect only.
    if over_flat > hi + 1e-12 and pos != 0 and dwell < min_dwell:
        return ParticipationDecision(
            MODE_FORCE_HOLD,
            (0.0, 0.5, stop, target),
            "over_flat_soft_min_dwell",
            suppress_flatten=True,
        )

    # PR-A: in-band max-dwell exit under active expectancy gap (real settlement only).
    if (
        bool(force_exit_on_expectancy_gap)
        and exp_gap > 1e-12
        and pos != 0
        and dwell >= max_hold
        and lo - 1e-12 <= under_flat
        and over_flat <= hi + 1e-12
    ):
        return _force_exit("in_band_expectancy_gap_max_dwell_exit")

    return ParticipationDecision(MODE_PASSTHROUGH, None, "in_band")


def participation_telemetry(counts: dict[str, int]) -> dict[str, int]:
    """Normalize counter dict for progress SSOT."""
    return {
        "participation_force_open": int(counts.get(MODE_FORCE_OPEN, 0) or 0),
        "participation_force_hold": int(counts.get(MODE_FORCE_HOLD, 0) or 0),
        "participation_force_flat": int(counts.get(MODE_FORCE_FLAT, 0) or 0),
        "participation_force_exit": int(counts.get(MODE_FORCE_EXIT, 0) or 0),
        "participation_passthrough": int(counts.get(MODE_PASSTHROUGH, 0) or 0),
        "participation_overrides_total": int(
            (counts.get(MODE_FORCE_OPEN, 0) or 0)
            + (counts.get(MODE_FORCE_HOLD, 0) or 0)
            + (counts.get(MODE_FORCE_FLAT, 0) or 0)
            + (counts.get(MODE_FORCE_EXIT, 0) or 0)
        ),
    }


__all__ = [
    "MODE_FORCE_EXIT",
    "MODE_FORCE_FLAT",
    "MODE_FORCE_HOLD",
    "MODE_FORCE_OPEN",
    "MODE_PASSTHROUGH",
    "ParticipationDecision",
    "ParticipationMode",
    "decide_stage2_participation",
    "force_open_stop_from_atr",
    "occupancy_control_flat",
    "occupancy_control_over",
    "participation_telemetry",
]
