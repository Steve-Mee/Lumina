"""S5 skill clock: volume min is necessary, not a stop-the-stage cap."""

from __future__ import annotations

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES, S5_MIN_TRADES
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
    """True → do not declare S5 terminal: skill sample can still grow.

    ``S5_MIN_TRADES`` (50) is a volume floor, not an exit. Idle + PASSTHROUGH
    + in-band + remaining ticks must be allowed to take the next policy close.
    """
    if stage != CurriculumStage.STAGE5_PROBE_HANDOFF:
        return False
    if int(policy_trades) >= int(POLICY_EDGE_MIN_TRADES):
        return False
    if int(stage_trades) < int(S5_MIN_TRADES):
        return False
    if not ticks_remaining:
        return False
    if str(participation_mode) != MODE_PASSTHROUGH:
        return False
    if not bool(idle_armed) or not bool(occupancy_in_band):
        return False
    return True


def skill_clock_open_from_loop(loop: object) -> bool:
    """Stage-loop adapter: remaining ticks + last envelope/idle HUD."""
    from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN

    occ = getattr(loop, "occupancy_control_flat", None)
    if occ is None:
        flat = int(getattr(loop, "stage_range_flat_bars", 0) or 0)
        sig = int(getattr(loop, "stage_range_total_signals", 0) or 0)
        occ = float(flat) / float(max(1, sig)) if sig else None
    in_band = occ is not None and (
        float(S3_OCCUPANCY_MIN) - 1e-12 <= float(occ) <= float(S3_OCCUPANCY_MAX) + 1e-12
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


__all__ = ["skill_clock_keeps_stage_open", "skill_clock_open_from_loop"]
