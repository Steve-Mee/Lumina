"""Stage-3 occupancy taxi — meta must not run Stage-2 expectancy swarm.

Live S3 2026-09-17: occupancy 0.24997, exam unarmed, meta rationale
``stage2_expectancy_swarm_*``. Explore-reduce cannot unstick the fencepost.
This module never lowers occupancy floors.
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import S3_OCCUPANCY_MIN


def stage3_occupancy_taxi_needed(
    *,
    stage: Any,
    occupancy: float | None,
    occupancy_exam_armed: bool | None = None,
    range_flat_ratio: float | None = None,
    range_total_signals: int = 0,
) -> bool:
    """True when S3/S4/S5 occupancy exam is unarmed and plant-flat is under exam_lo."""
    st = stage
    value = str(getattr(st, "value", st) or "").strip().lower()
    if value not in {
        CurriculumStage.STAGE3_MIXED.value,
        CurriculumStage.STAGE4_VIABLE_PLANT.value,
        CurriculumStage.STAGE5_PROBE_HANDOFF.value,
        "mixed",
        "stage3",
        "stage4",
        "viable_plant",
        "stage5",
        "probe_handoff",
    }:
        return False
    if occupancy_exam_armed is True:
        return False
    occ = occupancy if occupancy is not None else range_flat_ratio
    if occ is None:
        return False
    if int(range_total_signals) < 50 and occupancy is None:
        return False
    from lumina_core.birth.foundation_occupancy_envelope import EXAM_RECOVERY_SETTLE

    return float(occ) + 1e-12 < float(S3_OCCUPANCY_MIN) + EXAM_RECOVERY_SETTLE


def stage3_occupancy_meta_fields(
    *,
    exploration_steps: int,
    strong_recovery_explore_fraction: float,
) -> dict[str, Any]:
    explore = max(200, int(float(exploration_steps) * float(strong_recovery_explore_fraction)))
    return {
        "primary": "explore_reduce",
        "secondary": ["reward_shaping_tweak"],
        "explore_steps": explore,
        "escalation_delta": 1,
        "mine": False,
        "rationale": "stage3_occupancy_taxi",
    }


__all__ = [
    "stage3_occupancy_meta_fields",
    "stage3_occupancy_taxi_needed",
]
