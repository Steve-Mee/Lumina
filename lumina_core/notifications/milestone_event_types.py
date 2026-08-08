"""Birth milestone event taxonomy (ADR-0025)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_pass_receipt import StagePassReceipt

_STAGE_LABELS: dict[str, str] = {
    CurriculumStage.STAGE1_TREND.value: "Stage 1 — Trend",
    CurriculumStage.STAGE2_RANGE.value: "Stage 2 — Range",
    CurriculumStage.STAGE3_MIXED.value: "Stage 3 — Mixed",
    CurriculumStage.STAGE4_POLISH.value: "Stage 4 — Polish",
}

_STAGE_MILESTONE_IDS: dict[str, str] = {
    CurriculumStage.STAGE1_TREND.value: "curriculum_stage1_trend_passed",
    CurriculumStage.STAGE2_RANGE.value: "curriculum_stage2_range_passed",
    CurriculumStage.STAGE3_MIXED.value: "curriculum_stage3_mixed_passed",
    CurriculumStage.STAGE4_POLISH.value: "curriculum_stage4_polish_passed",
}


class MilestoneCategory(str, Enum):
    BIRTH = "birth"


@dataclass(frozen=True, slots=True)
class MilestoneEvent:
    milestone_id: str
    category: MilestoneCategory
    title: str
    summary: str
    context: dict[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""

    def __post_init__(self) -> None:
        if not self.dedupe_key:
            object.__setattr__(self, "dedupe_key", self.milestone_id)

    def telegram_body(self) -> str:
        lines = [self.summary]
        if self.context:
            ctx_parts: list[str] = []
            for key in (
                "training_mode",
                "trade_budget",
                "resumed",
                "tick_count",
                "real_data_pct",
                "holdout_days",
                "train_bars",
                "holdout_bars",
                "stage",
                "trades",
                "winrate",
                "required_trades",
                "provisional",
                "ppo_steps",
                "cumulative_trades",
                "oos_sharpe",
                "oos_winrate",
                "max_drawdown",
                "stages_passed",
            ):
                if key in self.context and self.context[key] is not None:
                    ctx_parts.append(f"{key}: {self.context[key]}")
            if ctx_parts:
                lines.append("\n".join(ctx_parts))
        return "\n".join(lines)

__all__ = [
    "MilestoneCategory",
    "MilestoneEvent",
    "_STAGE_LABELS",
    "_STAGE_MILESTONE_IDS",
]
