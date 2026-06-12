"""Birth curriculum stages (ADR-0014)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig


class CurriculumStage(str, Enum):
    STAGE1_TREND = "stage1_trend"
    STAGE2_RANGE = "stage2_range"
    STAGE3_MIXED = "stage3_mixed"
    STAGE4_POLISH = "stage4_polish"


@dataclass(slots=True)
class StageResult:
    stage: CurriculumStage
    trades: int
    wins: int
    hold_ratio: float
    passed: bool
    message: str


def filter_ticks_for_stage(stage: CurriculumStage, ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if stage == CurriculumStage.STAGE1_TREND:
        return [t for t in ticks if "TREND" in str(t.get("regime", "")).upper()]
    if stage == CurriculumStage.STAGE2_RANGE:
        return [t for t in ticks if str(t.get("regime", "NEUTRAL")).upper() in {"NEUTRAL", "RANGING"}]
    return list(ticks)


def stage_trade_target(stage: CurriculumStage, cfg: BirthCurriculumConfig) -> int:
    if stage == CurriculumStage.STAGE1_TREND:
        return cfg.stage1_trend_trades
    if stage == CurriculumStage.STAGE2_RANGE:
        return cfg.stage2_range_trades
    if stage == CurriculumStage.STAGE3_MIXED:
        return cfg.stage3_mixed_trades
    return 0


def evaluate_stage_pass(
    stage: CurriculumStage,
    *,
    trades: int,
    wins: int,
    hold_signals: int,
    total_signals: int,
    constitution_violations: int,
    target_trades: int,
) -> StageResult:
    winrate = float(wins) / float(max(1, trades))
    hold_ratio = float(hold_signals) / float(max(1, total_signals))
    passed = False
    message = ""

    if stage == CurriculumStage.STAGE1_TREND:
        passed = trades >= min(100, target_trades) and winrate >= 0.45
        message = f"trend winrate={winrate:.2%} trades={trades}"
    elif stage == CurriculumStage.STAGE2_RANGE:
        passed = trades >= min(100, target_trades) and 0.30 <= hold_ratio <= 0.70
        message = f"range hold_ratio={hold_ratio:.2%} trades={trades}"
    elif stage == CurriculumStage.STAGE3_MIXED:
        passed = trades >= min(100, target_trades) and constitution_violations == 0
        message = f"mixed violations={constitution_violations} trades={trades}"
    elif stage == CurriculumStage.STAGE4_POLISH:
        passed = True
        message = "polish complete"

    return StageResult(
        stage=stage,
        trades=trades,
        wins=wins,
        hold_ratio=hold_ratio,
        passed=passed,
        message=message,
    )


def ordered_stages() -> list[CurriculumStage]:
    return [
        CurriculumStage.STAGE1_TREND,
        CurriculumStage.STAGE2_RANGE,
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_POLISH,
    ]
