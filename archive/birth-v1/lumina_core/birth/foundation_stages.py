"""Sequential Birth Foundation stage identity (ADR-0046). 1/5–5/5, no skip."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import (
    FOUNDATION_STAGE_COUNT,
    S1_MIN_TRADES,
    S2_MIN_TRADES,
    S3_MIN_TRADES,
    S4_MIN_TRADES,
    S5_MIN_TRADES,
)

logger = logging.getLogger(__name__)

FOUNDATION_STAGES: tuple[CurriculumStage, ...] = (
    CurriculumStage.STAGE1_TREND,
    CurriculumStage.STAGE2_RANGE,
    CurriculumStage.STAGE3_MIXED,
    CurriculumStage.STAGE4_VIABLE_PLANT,
    CurriculumStage.STAGE5_PROBE_HANDOFF,
)

LEGACY_INTRA_BIRTH_STAGES: frozenset[CurriculumStage] = frozenset(
    {
        CurriculumStage.STAGE4_POLISH,
        CurriculumStage.STAGE5_PROFIT_VAL,
        CurriculumStage.STAGE6_RISK_DISCIPLINE,
        CurriculumStage.STAGE7_HOLDOUT_PROFILE,
    }
)

_DISPLAY_NAMES: dict[CurriculumStage, str] = {
    CurriculumStage.STAGE1_TREND: "Closed loop",
    CurriculumStage.STAGE2_RANGE: "Selectivity",
    CurriculumStage.STAGE3_MIXED: "Mixed regimes",
    CurriculumStage.STAGE4_VIABLE_PLANT: "Viable plant",
    CurriculumStage.STAGE5_PROBE_HANDOFF: "Probe & handoff",
}

_MAX_EPOCHS: dict[CurriculumStage, int] = {
    # S1–S3 keep the certified rollout budget (not a 2-epoch freeze).
    CurriculumStage.STAGE1_TREND: 200,
    CurriculumStage.STAGE2_RANGE: 200,
    CurriculumStage.STAGE3_MIXED: 200,
    CurriculumStage.STAGE4_VIABLE_PLANT: 2,
    CurriculumStage.STAGE5_PROBE_HANDOFF: 1,
}


def is_foundation_stage(stage: CurriculumStage) -> bool:
    return stage in FOUNDATION_STAGES


def is_legacy_intra_birth_stage(stage: CurriculumStage) -> bool:
    """Old S4 polish / S5–S7 runway numbering — incompatible with foundation resume."""
    return stage in LEGACY_INTRA_BIRTH_STAGES


def foundation_display_name(stage: CurriculumStage) -> str:
    return _DISPLAY_NAMES.get(stage, stage.value.replace("_", " ").title())


def foundation_index_for_stage(stage: CurriculumStage) -> int:
    try:
        return FOUNDATION_STAGES.index(stage) + 1
    except ValueError:
        return 0


def foundation_min_trades(stage: CurriculumStage, cfg: BirthCurriculumConfig | None = None) -> int:
    defaults = {
        CurriculumStage.STAGE1_TREND: S1_MIN_TRADES,
        CurriculumStage.STAGE2_RANGE: S2_MIN_TRADES,
        CurriculumStage.STAGE3_MIXED: S3_MIN_TRADES,
        CurriculumStage.STAGE4_VIABLE_PLANT: S4_MIN_TRADES,
        CurriculumStage.STAGE5_PROBE_HANDOFF: S5_MIN_TRADES,
    }
    base = int(defaults.get(stage, 50))
    if cfg is None:
        return base
    key = {
        CurriculumStage.STAGE1_TREND: "foundation_stage1_min_trades",
        CurriculumStage.STAGE2_RANGE: "foundation_stage2_min_trades",
        CurriculumStage.STAGE3_MIXED: "foundation_stage3_min_trades",
        CurriculumStage.STAGE4_VIABLE_PLANT: "foundation_stage4_min_trades",
        CurriculumStage.STAGE5_PROBE_HANDOFF: "foundation_stage5_min_trades",
    }.get(stage)
    if key is None:
        return base
    return max(base, int(getattr(cfg, key, base) or base))


def foundation_max_epochs(stage: CurriculumStage) -> int:
    return int(_MAX_EPOCHS.get(stage, 2))


def foundation_eval_only(stage: CurriculumStage) -> bool:
    """Stage 5 holdout is read-only (no PPO train loop)."""
    return stage == CurriculumStage.STAGE5_PROBE_HANDOFF


def ticks_for_foundation_stage(
    stage: CurriculumStage,
    *,
    train_ticks: list[dict[str, Any]],
    validation_ticks: list[dict[str, Any]] | None = None,
    holdout_ticks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | None:
    """Return stage ticks or None when the filter/slice is empty (fail-closed)."""
    from lumina_core.birth.curriculum_types import filter_ticks_for_stage

    if stage == CurriculumStage.STAGE1_TREND:
        filtered = filter_ticks_for_stage(stage, train_ticks)
        return filtered or None
    if stage == CurriculumStage.STAGE2_RANGE:
        filtered = filter_ticks_for_stage(stage, train_ticks)
        return filtered or None
    if stage == CurriculumStage.STAGE3_MIXED:
        return list(train_ticks) if train_ticks else None
    if stage == CurriculumStage.STAGE4_VIABLE_PLANT:
        val = list(validation_ticks or [])
        return val or None
    if stage == CurriculumStage.STAGE5_PROBE_HANDOFF:
        hold = list(holdout_ticks or [])
        return hold or None
    return None


def refresh_fail_closed_ticks_after_data_change(
    stage: CurriculumStage,
    *,
    train_ticks: list[dict[str, Any]],
    previous_stage_ticks: list[dict[str, Any]] | None,
    holdout_ticks: list[dict[str, Any]] | None,
    validation_pct: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Re-purge S4 val from expanded train. Other stages keep prior slice identity."""
    val = list(previous_stage_ticks or []) if previous_stage_ticks is not None else None
    if stage == CurriculumStage.STAGE4_VIABLE_PLANT:
        from lumina_core.birth.purged_split import purged_validation_split

        split = purged_validation_split(
            list(train_ticks),
            validation_pct=float(validation_pct),
        )
        val = list(split.validation)
    ticks = fail_closed_stage_ticks(
        stage,
        train_ticks=train_ticks,
        validation_ticks=val,
        holdout_ticks=holdout_ticks,
    )
    return list(val or []), ticks


def fail_closed_stage_ticks(
    stage: CurriculumStage,
    *,
    train_ticks: list[dict[str, Any]] | None = None,
    validation_ticks: list[dict[str, Any]] | None = None,
    holdout_ticks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Stage ticks with no silent fallback to full train (plan lock #3)."""
    ticks = ticks_for_foundation_stage(
        stage,
        train_ticks=list(train_ticks or []),
        validation_ticks=list(validation_ticks or []) if validation_ticks is not None else None,
        holdout_ticks=list(holdout_ticks or []) if holdout_ticks is not None else None,
    )
    if not ticks:
        logger.error("birth.foundation.empty_filter_fail_closed stage=%s", stage.value)
        return []
    return list(ticks)


__all__ = [
    "FOUNDATION_STAGE_COUNT",
    "FOUNDATION_STAGES",
    "LEGACY_INTRA_BIRTH_STAGES",
    "foundation_display_name",
    "foundation_eval_only",
    "foundation_index_for_stage",
    "foundation_max_epochs",
    "foundation_min_trades",
    "is_foundation_stage",
    "is_legacy_intra_birth_stage",
    "ticks_for_foundation_stage",
    "fail_closed_stage_ticks",
    "refresh_fail_closed_ticks_after_data_change",
]
