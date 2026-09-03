"""S5 occupancy continuity (Tooth A) + re-arm hysteresis constant (Tooth B).

S5 is a probe of the same organism. If S4 occupancy is in the exam band,
seed S5 cumulative flat from that number so the first bars are PASSTHROUGH.
Do not invent 0.50.
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MAX, S3_OCCUPANCY_MIN

REARM_HYST = 0.04
S5_SEED_SIGNALS = 200


def s4_occupancy_from_receipts(receipts: Any) -> float | None:
    """Real S4 occupancy or None. Never invent a midpoint."""
    rows = list(receipts or [])
    for rec in reversed(rows):
        stage = str(getattr(rec, "stage", "") or "")
        if not stage and isinstance(rec, dict):
            stage = str(rec.get("stage") or "")
        if stage != CurriculumStage.STAGE4_VIABLE_PLANT.value:
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


def s4_occupancy_in_s5_exam_band(occupancy: float | None) -> bool:
    if occupancy is None:
        return False
    return S3_OCCUPANCY_MIN - 1e-12 <= float(occupancy) <= S3_OCCUPANCY_MAX + 1e-12


def apply_s5_occupancy_seed(loop: Any) -> str:
    """Seed S5 occupancy clocks from the verified S4 receipt. Returns seed source."""
    stage = getattr(loop, "stage", None)
    if stage != CurriculumStage.STAGE5_PROBE_HANDOFF:
        loop.occupancy_seed_source = "n/a"
        loop.occupancy_seed_value = None
        loop.occupancy_in_band_seen = bool(getattr(loop, "occupancy_in_band_seen", False))
        return "n/a"
    host = getattr(loop, "host", None)
    receipts = getattr(host, "_stage_pass_receipts", None) if host is not None else None
    occ = s4_occupancy_from_receipts(receipts)
    loop.occupancy_seed_value = occ
    if not s4_occupancy_in_s5_exam_band(occ):
        src = "missing" if occ is None else "s4_out_of_band"
        loop.occupancy_seed_source = src
        loop.occupancy_in_band_seen = False
        return src
    n = int(S5_SEED_SIGNALS)
    seeded = float(occ)
    loop.stage_range_total_signals = n
    loop.stage_range_flat_bars = int(round(seeded * float(n)))
    loop.occupancy_control_flat = seeded
    loop.occupancy_in_band_seen = True
    loop.occupancy_seed_source = "s4_receipt"
    return "s4_receipt"


def s5_continuity_rollout_kwargs(loop: Any) -> dict[str, Any]:
    return {
        "occupancy_in_band_seen": bool(getattr(loop, "occupancy_in_band_seen", False)),
    }


__all__ = [
    "REARM_HYST",
    "S5_SEED_SIGNALS",
    "apply_s5_occupancy_seed",
    "s4_occupancy_from_receipts",
    "s4_occupancy_in_s5_exam_band",
    "s5_continuity_rollout_kwargs",
]
