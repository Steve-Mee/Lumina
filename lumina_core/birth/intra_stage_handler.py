"""IntraStageHandler — single responsibility for intra-stage difficulty progression.

Stage1 trend easy→hard and Stage2 range flat→active sampling logic.
Core pure functions live in curriculum.py. This module is the owner for
future event-driven intra pool sampling announcements.
"""

from __future__ import annotations

from lumina_core.birth.curriculum import (
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    sample_intra_stage1_pool,
    sample_intra_stage2_pool,
    split_stage1_trend_ticks,
    split_stage2_range_ticks,
    update_stage1_intra_state,
    update_stage2_intra_state,
)

__all__ = [
    "Stage1IntraCurriculumState",
    "Stage2IntraCurriculumState",
    "sample_intra_stage1_pool",
    "sample_intra_stage2_pool",
    "split_stage1_trend_ticks",
    "split_stage2_range_ticks",
    "update_stage1_intra_state",
    "update_stage2_intra_state",
]
