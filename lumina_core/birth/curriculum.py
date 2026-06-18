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
    provisional: bool = False
    range_hold_ratio: float = 0.0
    range_flat_ratio: float = 0.0
    range_round_trips: int = 0


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


def stage_pass_trades(stage: CurriculumStage, cfg: BirthCurriculumConfig) -> int:
    """Minimum cumulative trades required to graduate a curriculum stage."""
    target = stage_trade_target(stage, cfg)
    if target <= 0:
        return 50
    # Pass gate uses stage target from config (not a hard cap at 100).
    return max(50, min(target, max(100, target // 10)))


def stage_progress_pct(stage_trades: int, cfg: BirthCurriculumConfig, *, stage: CurriculumStage) -> float:
    required = stage_pass_trades(stage, cfg)
    if required <= 0:
        return 0.0
    return min(100.0, (float(stage_trades) / float(required)) * 100.0)


def should_gen0_soft_pass(
    *,
    stage_trades: int,
    buffer_size: int,
    attempt: int,
    cfg: BirthCurriculumConfig,
) -> bool:
    if attempt < cfg.max_rollouts_per_stage:
        return False
    if stage_trades < cfg.gen0_provisional_min_trades:
        return False
    return buffer_size >= 256


def evaluate_stage_pass(
    stage: CurriculumStage,
    *,
    trades: int,
    wins: int,
    hold_signals: int,
    total_signals: int,
    range_hold_signals: int = 0,
    range_total_signals: int = 0,
    range_flat_bars: int = 0,
    range_round_trips: int = 0,
    constitution_violations: int,
    target_trades: int,
    cfg: BirthCurriculumConfig | None = None,
    provisional: bool = False,
    allow_provisional: bool = False,
    oracle_patterns: int = 0,
    buffer_size: int = 0,
    oracle_soft_min_patterns: int = 100,
) -> StageResult:
    winrate = float(wins) / float(max(1, trades))
    hold_ratio = float(hold_signals) / float(max(1, total_signals))
    range_hold_ratio = float(range_hold_signals) / float(max(1, range_total_signals))
    range_flat_ratio = float(range_flat_bars) / float(max(1, range_total_signals))
    if cfg is not None:
        required = stage_pass_trades(stage, cfg)
    else:
        required = max(50, min(100, max(1, int(target_trades))))
    passed = False
    message = ""

    if stage == CurriculumStage.STAGE1_TREND:
        passed = trades >= required and winrate >= 0.45
        message = f"trend winrate={winrate:.2%} trades={trades}/{required}"
    elif stage == CurriculumStage.STAGE2_RANGE:
        if range_total_signals >= 50:
            metric = range_flat_ratio
            metric_label = "range_flat"
            min_round_trips = max(3, required // 10)
            passed = (
                trades >= required
                and 0.30 <= metric <= 0.70
                and range_round_trips >= min_round_trips
            )
            message = (
                f"{metric_label}_ratio={metric:.2%} round_trips={range_round_trips} "
                f"trades={trades}/{required} (range_ticks={range_total_signals})"
            )
        else:
            metric = hold_ratio
            metric_label = "hold"
            passed = trades >= required and 0.30 <= metric <= 0.70
            message = (
                f"{metric_label}_ratio={metric:.2%} trades={trades}/{required} "
                f"(range_ticks={range_total_signals})"
            )
    elif stage == CurriculumStage.STAGE3_MIXED:
        passed = trades >= required and constitution_violations == 0
        message = f"mixed violations={constitution_violations} trades={trades}/{required}"
    elif stage == CurriculumStage.STAGE4_POLISH:
        passed = True
        message = "polish complete"

    if allow_provisional and provisional and not passed and trades >= max(1, required // 4):
        passed = True
        message = f"{message} gen0_provisional"

    if (
        allow_provisional
        and not passed
        and oracle_patterns >= oracle_soft_min_patterns
        and buffer_size >= 256
        and trades >= max(1, required // 4)
    ):
        passed = True
        message = f"{message} oracle_soft_pass"

    if (
        allow_provisional
        and not passed
        and provisional
        and oracle_patterns >= oracle_soft_min_patterns
        and buffer_size >= max(80, oracle_soft_min_patterns)
        and trades >= 1
    ):
        passed = True
        message = f"{message} oracle_gen0_research_pass"

    return StageResult(
        stage=stage,
        trades=trades,
        wins=wins,
        hold_ratio=hold_ratio,
        passed=passed,
        message=message,
        provisional=provisional,
        range_hold_ratio=range_hold_ratio,
        range_flat_ratio=range_flat_ratio,
        range_round_trips=int(range_round_trips),
    )


def ordered_stages() -> list[CurriculumStage]:
    return [
        CurriculumStage.STAGE1_TREND,
        CurriculumStage.STAGE2_RANGE,
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_POLISH,
    ]
