"""Foundation occupancy continuity. Seed S3/S4/S5 from the previous receipt.

S2 30–70% is inside the S3 25–75% exam. Seeding S3 from S2 avoids the 8-bar
blender at stage start. Never invent 0.50.
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN
from lumina_core.birth.foundation_occupancy_envelope import occupancy_exam_band, occupancy_exam_in_band

REARM_HYST = 0.04
S5_SEED_SIGNALS = 200

_PREV_STAGE: dict[CurriculumStage, CurriculumStage] = {
    CurriculumStage.STAGE3_MIXED: CurriculumStage.STAGE2_RANGE,
    CurriculumStage.STAGE4_VIABLE_PLANT: CurriculumStage.STAGE3_MIXED,
    CurriculumStage.STAGE5_PROBE_HANDOFF: CurriculumStage.STAGE4_VIABLE_PLANT,
}


def occupancy_from_receipts(receipts: Any, stage: CurriculumStage) -> float | None:
    """Real occupancy for ``stage`` or None. Never invent a midpoint."""
    want = str(getattr(stage, "value", stage) or "")
    rows = list(receipts or [])
    for rec in reversed(rows):
        got = str(getattr(rec, "stage", "") or "")
        if not got and isinstance(rec, dict):
            got = str(rec.get("stage") or "")
        if got != want:
            continue
        raw = getattr(rec, "occupancy", None)
        if raw is None and isinstance(rec, dict):
            raw = rec.get("occupancy")
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
    return None


def s4_occupancy_from_receipts(receipts: Any) -> float | None:
    """Real S4 occupancy or None. Never invent a midpoint."""
    return occupancy_from_receipts(receipts, CurriculumStage.STAGE4_VIABLE_PLANT)


def s4_occupancy_in_s5_exam_band(occupancy: float | None) -> bool:
    if occupancy is None:
        return False
    return S3_OCCUPANCY_MIN - 1e-12 <= float(occupancy) <= S3_OCCUPANCY_MAX + 1e-12


def apply_foundation_occupancy_seed(loop: Any) -> str:
    """Seed occupancy IMU from the previous foundation receipt when in-band."""
    stage = getattr(loop, "stage", None)
    prev = _PREV_STAGE.get(stage) if isinstance(stage, CurriculumStage) else None
    if prev is None:
        loop.occupancy_seed_source = "n/a"
        loop.occupancy_seed_value = None
        loop.occupancy_in_band_seen = bool(getattr(loop, "occupancy_in_band_seen", False))
        return "n/a"
    host = getattr(loop, "host", None)
    receipts = getattr(host, "_stage_pass_receipts", None) if host is not None else None
    occ = occupancy_from_receipts(receipts, prev)
    loop.occupancy_seed_value = occ
    lo, hi = occupancy_exam_band(stage)
    if not occupancy_exam_in_band(occ, lo=lo, hi=hi):
        src = "missing" if occ is None else f"{prev.value}_out_of_band"
        loop.occupancy_seed_source = src
        loop.occupancy_in_band_seen = False
        return src
    n = int(S5_SEED_SIGNALS)
    seeded = float(occ)
    loop.stage_range_total_signals = n
    loop.stage_range_flat_bars = int(round(seeded * float(n)))
    loop.occupancy_control_flat = seeded
    loop.occupancy_in_band_seen = True
    src = f"{prev.value}_receipt"
    loop.occupancy_seed_source = src
    return src


def apply_s5_occupancy_seed(loop: Any) -> str:
    """S5 alias: keep historical source tokens ``s4_receipt`` / ``s4_out_of_band``."""
    src = apply_foundation_occupancy_seed(loop)
    if src == "stage4_viable_plant_receipt":
        loop.occupancy_seed_source = "s4_receipt"
        return "s4_receipt"
    if src == "stage4_viable_plant_out_of_band":
        loop.occupancy_seed_source = "s4_out_of_band"
        return "s4_out_of_band"
    return src


def s5_continuity_rollout_kwargs(loop: Any) -> dict[str, Any]:
    return {
        "occupancy_in_band_seen": bool(getattr(loop, "occupancy_in_band_seen", False)),
    }


__all__ = [
    "REARM_HYST",
    "S5_SEED_SIGNALS",
    "apply_foundation_occupancy_seed",
    "apply_s5_occupancy_seed",
    "occupancy_from_receipts",
    "s4_occupancy_from_receipts",
    "s4_occupancy_in_s5_exam_band",
    "s5_continuity_rollout_kwargs",
]
