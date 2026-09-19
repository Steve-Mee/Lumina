"""S5 skill clock: volume min is necessary, not a stop-the-stage cap."""

from __future__ import annotations

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S4_MIN_TRADES,
    S5_DD_MAX_PCT,
    S5_MIN_TRADES,
)
from lumina_core.birth.stage2_participation_envelope import MODE_PASSTHROUGH


def skill_clock_keeps_stage_open(
    *,
    stage: CurriculumStage,
    stage_trades: int,
    policy_trades: int,
    ticks_remaining: bool,
    participation_mode: str,
    idle_armed: bool,
    occupancy_in_band: bool,
) -> bool:
    """True → do not declare S4/S5 terminal: skill sample can still grow.

    Live S4: policy 131 < 150 while other gates were green, then HOLD stall.
    Volume floors are necessary, not an exit. Idle + PASSTHROUGH + in-band
    + remaining ticks must be allowed to take the next policy close.
    """
    if stage not in (
        CurriculumStage.STAGE4_VIABLE_PLANT,
        CurriculumStage.STAGE5_PROBE_HANDOFF,
    ):
        return False
    if int(policy_trades) >= int(POLICY_EDGE_MIN_TRADES):
        return False
    vol_floor = (
        int(S4_MIN_TRADES)
        if stage == CurriculumStage.STAGE4_VIABLE_PLANT
        else int(S5_MIN_TRADES)
    )
    if int(stage_trades) < vol_floor:
        return False
    if not ticks_remaining:
        return False
    if str(participation_mode) != MODE_PASSTHROUGH:
        return False
    if not bool(occupancy_in_band):
        return False
    _ = idle_armed
    return True


def skill_clock_open_from_loop(loop: object) -> bool:
    """Stage-loop adapter: remaining ticks + last envelope/idle HUD."""
    from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN
    from lumina_core.birth.foundation_occupancy_envelope import occupancy_under_exam_fencepost

    occ = getattr(loop, "occupancy_control_flat", None)
    if occ is None:
        flat = int(getattr(loop, "stage_range_flat_bars", 0) or 0)
        sig = int(getattr(loop, "stage_range_total_signals", 0) or 0)
        occ = float(flat) / float(max(1, sig)) if sig else None
    in_band = occ is not None and (
        float(S3_OCCUPANCY_MIN) - 1e-12 <= float(occ) <= float(S3_OCCUPANCY_MAX) + 1e-12
        or occupancy_under_exam_fencepost(occ)
    )
    ticks_left = not bool(getattr(loop, "data_exhausted", False))
    return skill_clock_keeps_stage_open(
        stage=getattr(loop, "stage"),
        stage_trades=int(getattr(loop, "stage_trades", 0) or 0),
        policy_trades=int(getattr(loop, "stage_policy_trades", 0) or 0),
        ticks_remaining=ticks_left,
        participation_mode=str(getattr(loop, "participation_last_mode", "") or ""),
        idle_armed=bool(getattr(loop, "s3_inband_idle_armed", False)),
        occupancy_in_band=in_band,
    )


def s5_holdout_exam_stop_reason(
    *,
    eval_only: bool,
    oos_dd_pct: float | None,
    data_exhausted: bool,
    stage_trades: int,
) -> str | None:
    """Holdout probe stop: DD breach is terminal; tape end ends the exam.

    Stacking 13 restarts of the same 16 days onto one $50k curve is not an exam.
    Floors stay pinned (25% of $50k).
    """
    if not eval_only:
        return None
    if oos_dd_pct is not None and float(oos_dd_pct) > S5_DD_MAX_PCT + 1e-12:
        return "s5_holdout_dd_exceeded"
    if data_exhausted and int(stage_trades) >= 0:
        return "s5_holdout_tape_exhausted"
    return None


__all__ = [
    "s5_holdout_exam_stop_reason",
    "skill_clock_keeps_stage_open",
    "skill_clock_open_from_loop",
]
