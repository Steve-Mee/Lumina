"""Shared occupancy envelope airframe for foundation stages that grade occupancy.

Exam floors stay in ``foundation_metrics`` (S2 [0.30, 0.70], S3/S4/S5 [0.25, 0.75]).
Controller: S2 stays S2 numbers; S3/S4/S5 stay the S3 controller (lo=0.28 hi=0.72,
hyst=0.0, ``cumulative_in_band_passthrough``). Dual IMU is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.curriculum_types import CurriculumStage

S3_CONTROLLER_STAGES = frozenset(
    {
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_VIABLE_PLANT,
        CurriculumStage.STAGE5_PROBE_HANDOFF,
    }
)

# Stage.value plus HUD aliases. S2 is intentionally absent (dual IMU, no
# cumulative-in-band PASSTHROUGH override).
S3_CONTROLLER_REGIMES = frozenset(
    {
        "mixed",
        "stage3_mixed",
        "stage3",
        "stage4_viable_plant",
        "stage4",
        "viable_plant",
        "stage5_probe_handoff",
        "stage5",
        "probe_handoff",
    }
)


def foundation_occupancy_envelope_enabled(stage: CurriculumStage, cfg: Any) -> bool:
    """True for every foundation stage that grades occupancy (S2–S5)."""
    if stage == CurriculumStage.STAGE2_RANGE:
        return bool(getattr(cfg, "stage2_participation_envelope_enabled", True))
    if stage == CurriculumStage.STAGE3_MIXED:
        return bool(getattr(cfg, "stage3_participation_envelope_enabled", True))
    if stage == CurriculumStage.STAGE4_VIABLE_PLANT:
        return bool(getattr(cfg, "stage4_participation_envelope_enabled", True))
    if stage == CurriculumStage.STAGE5_PROBE_HANDOFF:
        return bool(getattr(cfg, "stage5_participation_envelope_enabled", True))
    return False


def foundation_envelope_uses_s3_controller(stage: CurriculumStage) -> bool:
    """S3/S4/S5 share the S3 controller. S2 keeps its own bands / release hyst."""
    return stage in S3_CONTROLLER_STAGES


def foundation_cumulative_in_band_passthrough(curriculum_regime: str) -> bool:
    """S3/S4/S5: exam-in-band cumulative owns PASSTHROUGH. S2 dual IMU stays off."""
    return str(curriculum_regime or "").strip().lower() in S3_CONTROLLER_REGIMES


@dataclass(frozen=True, slots=True)
class EnvelopeControllerSpec:
    band_lo: float
    band_hi: float
    hysteresis: float
    release_hysteresis: float
    min_signals_attr: str
    min_dwell_attr: str
    window_attr: str


def foundation_envelope_controller_spec(stage: CurriculumStage, cfg: Any) -> EnvelopeControllerSpec:
    """Resolve live controller numbers. Does not touch exam floors."""
    uses_s3 = foundation_envelope_uses_s3_controller(stage)
    hyst_default = 0.0 if uses_s3 else 0.02
    lo_default = 0.28 if uses_s3 else 0.30
    hi_default = 0.72 if uses_s3 else 0.70
    rel_default = 0.0 if uses_s3 else 0.02
    hyst_raw = getattr(
        cfg,
        "stage3_participation_hysteresis" if uses_s3 else "stage2_participation_hysteresis",
        hyst_default,
    )
    hysteresis = float(hyst_default if hyst_raw is None else hyst_raw)
    rel_raw = getattr(
        cfg,
        (
            "stage3_participation_under_band_release_hysteresis"
            if uses_s3
            else "stage2_participation_under_band_release_hysteresis"
        ),
        rel_default,
    )
    release_hysteresis = float(rel_default if rel_raw is None else rel_raw)
    # Stage-2: 0.0 release hyst pins occupancy at 0.2996. Floor 0.02.
    if not uses_s3 and release_hysteresis < 0.02 - 1e-12:
        release_hysteresis = 0.02
    lo_raw = getattr(
        cfg,
        "stage3_participation_band_lo" if uses_s3 else "stage2_participation_band_lo",
        lo_default,
    )
    hi_raw = getattr(
        cfg,
        "stage3_participation_band_hi" if uses_s3 else "stage2_participation_band_hi",
        hi_default,
    )
    return EnvelopeControllerSpec(
        band_lo=float(lo_default if lo_raw is None else lo_raw),
        band_hi=float(hi_default if hi_raw is None else hi_raw),
        hysteresis=hysteresis,
        release_hysteresis=release_hysteresis,
        min_signals_attr=(
            "stage3_participation_min_signals" if uses_s3 else "stage2_participation_min_signals"
        ),
        min_dwell_attr=(
            "stage3_participation_min_dwell_bars" if uses_s3 else "stage2_participation_min_dwell_bars"
        ),
        window_attr=(
            "stage3_occupancy_control_window_bars" if uses_s3 else "stage2_occupancy_control_window_bars"
        ),
    )


__all__ = [
    "EnvelopeControllerSpec",
    "S3_CONTROLLER_REGIMES",
    "S3_CONTROLLER_STAGES",
    "foundation_cumulative_in_band_passthrough",
    "foundation_envelope_controller_spec",
    "foundation_envelope_uses_s3_controller",
    "foundation_occupancy_envelope_enabled",
]
