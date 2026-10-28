"""Shared occupancy envelope airframe for foundation stages that grade occupancy.

Exam floors stay in ``foundation_metrics`` (S2 [0.30, 0.70], S3/S4/S5 [0.25, 0.75]).
Controller: S2 stays S2 numbers; S3/S4/S5 stay the S3 controller (lo=0.28 hi=0.72,
hyst=0.0). Dual IMU is unchanged.

S3/S4/S5 ``cumulative_in_band_passthrough`` is exam-band law (0.25–0.75), not the
tighter controller. Occupancy 0.2799 is exam-in-band; pinning FORCE_HOLD at
controller 0.28 is the 0.2996 fencepost reincarnated.

Empty exam PASSTHROUGH settles ``EXAM_RECOVERY_SETTLE`` (2pp) inside exam_lo
**only while climbing** (``in_band_seen=False``). After the exam is seen,
empty is PASSTHROUGH so policy-owned flats count. Live S4: plant-flat 0.2694
with 12546 FORCE_FLAT vs 723 exam flats — a 0.27 settle under in-position
PASSTHROUGH is a treadmill and starves exam occupancy (2.38%). Floors unchanged.

Pass rejects ``envelope_override_fraction > 0.5`` on the **exam window**, not
lifetime airframe ticks. Taxi (plant-flat outside the exam band) may be
envelope-owned; that is training wheels, not the exam. Once plant-flat is in
band, the policy must hold the band on PASSTHROUGH. Leaving the band resets
the window (fail-closed). Lifetime override stays HUD-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import (
    S2_OCCUPANCY_MAX,
    S2_OCCUPANCY_MIN,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
)

OCCUPANCY_EXAM_MIN_PASSTHROUGH = 50
# After under-exam recovery, empty must settle this far inside exam_lo before
# PASSTHROUGH re-entry. Same 2pp as S2 0.2996. Never lowers the 25% floor.
EXAM_RECOVERY_SETTLE = 0.02
OCCUPANCY_FENCEPOST_HAIRLINE = 0.01

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


def envelope_override_fraction(passthrough: int, overrides: int) -> float | None:
    """Share of occupancy ticks the envelope owned. None when the envelope is idle."""
    total = int(passthrough) + int(overrides)
    if total <= 0:
        return None
    return float(overrides) / float(total)


@dataclass(frozen=True, slots=True)
class OccupancyExamWindow:
    """Occupancy exam while plant-flat is in-band. Resets on a true band exit."""

    armed: bool = False
    passthrough: int = 0
    overrides: int = 0
    passthrough_flat: int = 0
    passthrough_signals: int = 0
    # All ticks while armed (plant-flat). PASSTHROUGH-only empty% starves to
    # ~4% (live S3) because empty bars are FORCE_FLAT overrides, not policy.
    exam_flat: int = 0
    exam_signals: int = 0

    @property
    def ready(self) -> bool:
        n = int(self.exam_signals) or int(self.passthrough_signals)
        return bool(self.armed) and n >= OCCUPANCY_EXAM_MIN_PASSTHROUGH


def occupancy_exam_band(stage: CurriculumStage) -> tuple[float, float]:
    if stage == CurriculumStage.STAGE2_RANGE:
        return S2_OCCUPANCY_MIN, S2_OCCUPANCY_MAX
    return S3_OCCUPANCY_MIN, S3_OCCUPANCY_MAX


def occupancy_exam_in_band(flat: float | None, *, lo: float, hi: float) -> bool:
    if flat is None:
        return False
    return float(lo) - 1e-12 <= float(flat) <= float(hi) + 1e-12


def exam_empty_settle_lo(exam_lo: float, release_hyst: float) -> float:
    """Empty PASSTHROUGH floor: exam_lo + max(yaml hyst, 2pp settle)."""
    return float(exam_lo) + max(float(release_hyst), EXAM_RECOVERY_SETTLE)


def occupancy_under_exam_fencepost(
    occupancy: float | None,
    *,
    exam_lo: float | None = None,
    hairline: float = OCCUPANCY_FENCEPOST_HAIRLINE,
) -> bool:
    """True when plant-flat sits just under exam_lo (live 0.24996 / 0.2477)."""
    if occupancy is None:
        return False
    lo = float(S3_OCCUPANCY_MIN if exam_lo is None else exam_lo)
    occ = float(occupancy)
    width = max(0.0, float(hairline))
    return (lo - width) - 1e-12 <= occ < lo - 1e-12


def occupancy_fencepost_blocks_expand(
    *,
    occupancy: float | None,
    occupancy_exam_armed: bool | None = None,
    exam_lo: float | None = None,
) -> bool:
    """Expand-data cannot fix an unarmed exam below settle (live 0.23998 blender)."""
    if occupancy_exam_armed is True:
        return False
    if occupancy is None:
        return False
    lo = float(S3_OCCUPANCY_MIN if exam_lo is None else exam_lo)
    return float(occupancy) + 1e-12 < lo + EXAM_RECOVERY_SETTLE


def step_occupancy_exam_window(
    window: OccupancyExamWindow | None,
    *,
    plant_flat: float,
    exam_lo: float,
    exam_hi: float,
    passthrough: bool,
    empty: bool,
) -> OccupancyExamWindow:
    """Arm while plant-flat is in-band; reset on a true exit. Counts this tick."""
    prev = window if isinstance(window, OccupancyExamWindow) else OccupancyExamWindow()
    if occupancy_exam_in_band(plant_flat, lo=exam_lo, hi=exam_hi):
        is_pt = bool(passthrough)
        return OccupancyExamWindow(
            armed=True,
            passthrough=int(prev.passthrough) + (1 if is_pt else 0),
            overrides=int(prev.overrides) + (0 if is_pt else 1),
            passthrough_flat=int(prev.passthrough_flat) + (1 if is_pt and empty else 0),
            passthrough_signals=int(prev.passthrough_signals) + (1 if is_pt else 0),
            exam_flat=int(prev.exam_flat) + (1 if empty else 0),
            exam_signals=int(prev.exam_signals) + 1,
        )
    # Live S4 0.2496: hairline must not wipe an armed exam (6/7→4/7).
    # Crash below 0.24 still resets. Hairline ticks are not counted.
    if prev.armed and occupancy_under_exam_fencepost(plant_flat, exam_lo=exam_lo):
        return prev
    return OccupancyExamWindow()


def exam_window_override_fraction(window: OccupancyExamWindow | None) -> float | None:
    if not isinstance(window, OccupancyExamWindow) or not window.armed:
        return None
    return envelope_override_fraction(window.passthrough, window.overrides)


def loop_envelope_scorecard_kwargs(host: Any) -> dict[str, Any]:
    """HUD/pass occupancy inputs from a live stage-loop host. Never invent ticks."""
    passthrough = int(getattr(host, "participation_passthrough", 0) or 0)
    overrides = int(getattr(host, "participation_overrides_total", 0) or 0)
    raw_win = getattr(host, "occupancy_exam_window", None)
    win = raw_win if isinstance(raw_win, OccupancyExamWindow) else OccupancyExamWindow()
    exam_frac = exam_window_override_fraction(win)
    return {
        "envelope_override_fraction": exam_frac,
        "airframe_override_fraction": envelope_override_fraction(passthrough, overrides),
        "passthrough_range_flat_bars": int(getattr(host, "passthrough_range_flat_bars", 0) or 0),
        "passthrough_range_total_signals": int(getattr(host, "passthrough_range_total_signals", 0) or 0),
        "exam_passthrough_flat_bars": int(win.passthrough_flat),
        "exam_passthrough_total_signals": int(win.passthrough_signals),
        "exam_flat_bars": int(win.exam_flat),
        "exam_total_signals": int(win.exam_signals),
        "occupancy_exam_armed": bool(win.armed),
    }


def occupancy_for_foundation_pass(
    *,
    stage: CurriculumStage,
    range_flat_bars: int,
    range_total_signals: int,
    passthrough_flat_bars: int = 0,
    passthrough_total_signals: int = 0,
    exam_armed: bool | None = None,
    exam_passthrough_flat_bars: int = 0,
    exam_passthrough_total_signals: int = 0,
    exam_flat_bars: int = 0,
    exam_total_signals: int = 0,
) -> float | None:
    """Pass occupancy.

    Exam window (armed): plant-flat over **all** in-band ticks. PASSTHROUGH-only
    empty% is biased (live S3 4% while plant-flat 25%). Thin window → None.
    Envelope override >50% is a separate blocker. S1 is None.
    """
    if stage == CurriculumStage.STAGE1_TREND:
        return None
    if exam_armed is True:
        all_n = int(exam_total_signals)
        if all_n >= OCCUPANCY_EXAM_MIN_PASSTHROUGH:
            return float(exam_flat_bars) / float(all_n)
        exam_n = int(exam_passthrough_total_signals)
        if exam_n >= OCCUPANCY_EXAM_MIN_PASSTHROUGH:
            return float(exam_passthrough_flat_bars) / float(exam_n)
        return None
    if exam_armed is False:
        tot = int(range_total_signals)
        if tot <= 0:
            return None
        plant = float(range_flat_bars) / float(tot)
        lo, hi = occupancy_exam_band(stage)
        if occupancy_exam_in_band(plant, lo=lo, hi=hi):
            return None
        return plant
    pt_tot = int(passthrough_total_signals)
    if pt_tot >= OCCUPANCY_EXAM_MIN_PASSTHROUGH:
        return float(passthrough_flat_bars) / float(pt_tot)
    tot = int(range_total_signals)
    if tot > 0:
        return float(range_flat_bars) / float(tot)
    return None


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
        min_signals_attr=("stage3_participation_min_signals" if uses_s3 else "stage2_participation_min_signals"),
        min_dwell_attr=("stage3_participation_min_dwell_bars" if uses_s3 else "stage2_participation_min_dwell_bars"),
        window_attr=("stage3_occupancy_control_window_bars" if uses_s3 else "stage2_occupancy_control_window_bars"),
    )


__all__ = [
    "EXAM_RECOVERY_SETTLE",
    "EnvelopeControllerSpec",
    "OCCUPANCY_EXAM_MIN_PASSTHROUGH",
    "OCCUPANCY_FENCEPOST_HAIRLINE",
    "OccupancyExamWindow",
    "S3_CONTROLLER_REGIMES",
    "S3_CONTROLLER_STAGES",
    "envelope_override_fraction",
    "exam_empty_settle_lo",
    "exam_window_override_fraction",
    "foundation_cumulative_in_band_passthrough",
    "foundation_envelope_controller_spec",
    "foundation_envelope_uses_s3_controller",
    "foundation_occupancy_envelope_enabled",
    "loop_envelope_scorecard_kwargs",
    "occupancy_exam_band",
    "occupancy_exam_in_band",
    "occupancy_fencepost_blocks_expand",
    "occupancy_for_foundation_pass",
    "occupancy_under_exam_fencepost",
    "step_occupancy_exam_window",
]
