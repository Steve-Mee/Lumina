"""Birth curriculum stages (ADR-0014) + Stage 1 intra easy→hard curriculum (ADR-0020).

Canonical import surface — implementation split into:
- curriculum_types.py (stages, targets, ordered stages)
- curriculum_intra.py (stage1/2 easy→hard pools)
- curriculum_pass.py (evaluate_stage_pass)
"""
from __future__ import annotations

from lumina_core.birth.curriculum_intra import (  # noqa: F401
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    sample_intra_stage1_pool,
    sample_intra_stage2_pool,
    split_stage1_trend_ticks,
    split_stage2_range_ticks,
    stage1_intra_state_from_metrics,
    stage1_trend_difficulty_score,
    stage2_intra_state_from_metrics,
    stage2_range_patience_score,
    update_stage1_intra_state,
    update_stage2_intra_state,
)
from lumina_core.birth.curriculum_pass import evaluate_stage_pass  # noqa: F401
from lumina_core.birth.curriculum_types import (  # noqa: F401
    MIN_INTRA_POOL_TICKS,
    CurriculumStage,
    StageResult,
    constitution_blocks_graduation,
    dynamic_stages,
    filter_ticks_for_stage,
    graduation_requires_clean_constitution,
    is_core_curriculum_stage,
    is_runway_stage,
    ordered_runway_stages,
    ordered_stages,
    should_gen0_soft_pass,
    stage1_winrate_pass_threshold,
    stage1_winrate_recommended,
    stage_pass_trades,
    stage_progress_pct,
    stage_trade_target,
)

__all__ = [
    "MIN_INTRA_POOL_TICKS",
    "CurriculumStage",
    "StageResult",
    "Stage1IntraCurriculumState",
    "Stage2IntraCurriculumState",
    "constitution_blocks_graduation",
    "dynamic_stages",
    "evaluate_stage_pass",
    "filter_ticks_for_stage",
    "graduation_requires_clean_constitution",
    "is_core_curriculum_stage",
    "is_runway_stage",
    "ordered_runway_stages",
    "ordered_stages",
    "sample_intra_stage1_pool",
    "sample_intra_stage2_pool",
    "should_gen0_soft_pass",
    "split_stage1_trend_ticks",
    "split_stage2_range_ticks",
    "stage1_intra_state_from_metrics",
    "stage1_trend_difficulty_score",
    "stage1_winrate_pass_threshold",
    "stage1_winrate_recommended",
    "stage2_intra_state_from_metrics",
    "stage2_range_patience_score",
    "stage_pass_trades",
    "stage_progress_pct",
    "stage_trade_target",
    "update_stage1_intra_state",
    "update_stage2_intra_state",
]
