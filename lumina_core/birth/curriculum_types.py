"""Birth curriculum stages (ADR-0014) + Stage 1/2 intra curriculum (ADR-0020)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig

MIN_INTRA_POOL_TICKS = 100

class CurriculumStage(str, Enum):
    STAGE1_TREND = "stage1_trend"
    STAGE2_RANGE = "stage2_range"
    STAGE3_MIXED = "stage3_mixed"
    STAGE4_VIABLE_PLANT = "stage4_viable_plant"
    STAGE5_PROBE_HANDOFF = "stage5_probe_handoff"
    # Legacy intra-Birth numbering — parse-compatible, not in ordered_stages().
    STAGE4_POLISH = "stage4_polish"
    STAGE5_PROFIT_VAL = "stage5_profit_val"
    STAGE6_RISK_DISCIPLINE = "stage6_risk_discipline"
    STAGE7_HOLDOUT_PROFILE = "stage7_holdout_profile"


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
    closes_stop: int = 0
    closes_target: int = 0
    closes_time_stop: int = 0
    closes_flatten: int = 0
    closes_unknown: int = 0
    occupancy: float | None = None
    median_loss_r: float | None = None
    mean_r: float | None = None
    edge: float | None = None
    p_ft: float | None = None
    e_mech: float | None = None
    net_rr: float | None = None
    unique_calendar_days: int | None = None
    oos_sharpe: float | None = None
    oos_dd_pct: float | None = None
    schema: str = "foundation_v2"
    settlement_ok: bool = True
    settlement_share: float = 1.0
    entropy_alive: bool = True
    replay_ok: bool = False
    progress_fields: dict[str, Any] = field(default_factory=dict)


def filter_ticks_for_stage(stage: CurriculumStage, ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if stage == CurriculumStage.STAGE1_TREND:
        return [t for t in ticks if "TREND" in str(t.get("regime", "")).upper()]
    if stage == CurriculumStage.STAGE2_RANGE:
        return [t for t in ticks if str(t.get("regime", "NEUTRAL")).upper() in {"NEUTRAL", "RANGING"}]
    if stage in {
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_VIABLE_PLANT,
        CurriculumStage.STAGE5_PROBE_HANDOFF,
        CurriculumStage.STAGE5_PROFIT_VAL,
        CurriculumStage.STAGE6_RISK_DISCIPLINE,
        CurriculumStage.STAGE7_HOLDOUT_PROFILE,
    }:
        return list(ticks)
    return list(ticks)


def stage_trade_target(stage: CurriculumStage, cfg: BirthCurriculumConfig) -> int:
    if stage == CurriculumStage.STAGE1_TREND:
        return cfg.stage1_trend_trades
    if stage == CurriculumStage.STAGE2_RANGE:
        return cfg.stage2_range_trades
    if stage == CurriculumStage.STAGE3_MIXED:
        return cfg.stage3_mixed_trades
    if stage == CurriculumStage.STAGE4_VIABLE_PLANT:
        return int(getattr(cfg, "stage4_viable_trades", 800))
    if stage == CurriculumStage.STAGE5_PROBE_HANDOFF:
        return int(getattr(cfg, "stage5_probe_trades", 200))
    if stage == CurriculumStage.STAGE5_PROFIT_VAL:
        return int(getattr(cfg, "stage5_profit_val_trades", 3000))
    if stage == CurriculumStage.STAGE6_RISK_DISCIPLINE:
        return int(getattr(cfg, "stage6_risk_discipline_trades", 2000))
    if stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
        return int(getattr(cfg, "stage7_holdout_profile_trades", 4000))
    return 0


def stage_pass_trades(stage: CurriculumStage, cfg: BirthCurriculumConfig) -> int:
    """Minimum closed trades required to graduate a foundation stage."""
    from lumina_core.birth.foundation_metrics import (
        S1_MIN_TRADES,
        S2_MIN_TRADES,
        S3_MIN_TRADES,
        S4_MIN_TRADES,
        S5_MIN_TRADES,
    )

    floors = {
        CurriculumStage.STAGE1_TREND: (
            S1_MIN_TRADES,
            "foundation_stage1_min_trades",
        ),
        CurriculumStage.STAGE2_RANGE: (
            S2_MIN_TRADES,
            "foundation_stage2_min_trades",
        ),
        CurriculumStage.STAGE3_MIXED: (
            S3_MIN_TRADES,
            "foundation_stage3_min_trades",
        ),
        CurriculumStage.STAGE4_VIABLE_PLANT: (
            S4_MIN_TRADES,
            "foundation_stage4_min_trades",
        ),
        CurriculumStage.STAGE5_PROBE_HANDOFF: (
            S5_MIN_TRADES,
            "foundation_stage5_min_trades",
        ),
    }
    if stage in floors:
        base, key = floors[stage]
        return max(int(base), int(getattr(cfg, key, base) or base))
    target = stage_trade_target(stage, cfg)
    if target <= 0:
        return 50
    pct = max(0.05, min(1.0, float(cfg.stage_pass_trade_pct)))
    floor = max(50, int(cfg.stage_pass_min_trades))
    computed = max(floor, int(round(float(target) * pct)))
    return max(50, min(target, computed))


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


def stage1_winrate_pass_threshold(cfg: BirthCurriculumConfig) -> float:
    """SSOT for stage1 trend winrate graduation gate (clamped to floor)."""
    floor = float(getattr(cfg, "stage1_winrate_pass_floor", 0.35))
    threshold = float(getattr(cfg, "stage1_winrate_pass_threshold", 0.45))
    return max(floor, min(0.60, threshold))


def stage1_winrate_recommended(cfg: BirthCurriculumConfig) -> float:
    return float(getattr(cfg, "stage1_winrate_recommended", 0.45))


def graduation_requires_clean_constitution(stage: CurriculumStage) -> bool:
    return stage in {
        CurriculumStage.STAGE1_TREND,
        CurriculumStage.STAGE2_RANGE,
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_VIABLE_PLANT,
        CurriculumStage.STAGE5_PROBE_HANDOFF,
    }


def constitution_blocks_graduation(
    *,
    stage: CurriculumStage,
    constitution_violations: int,
) -> bool:
    return graduation_requires_clean_constitution(stage) and constitution_violations > 0


def ordered_stages() -> list[CurriculumStage]:
    """Sequential Birth Foundation 1/5–5/5. No polish skip, no intra-Birth runway."""
    return [
        CurriculumStage.STAGE1_TREND,
        CurriculumStage.STAGE2_RANGE,
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_VIABLE_PLANT,
        CurriculumStage.STAGE5_PROBE_HANDOFF,
    ]


def dynamic_stages(workspace_root: Path | str | None = None) -> list[dict[str, Any]]:
    """Post-gen0 self-authored milestones (M16+) for evolution orchestration."""
    if workspace_root is None:
        return []
    from lumina_core.evolution.meta_milestones import dynamic_stage_specs

    return dynamic_stage_specs(workspace_root)


def ordered_runway_stages() -> list[CurriculumStage]:
    """Legacy runway enums — post-Birth proving/cert only, not Birth numbering."""
    return [
        CurriculumStage.STAGE5_PROFIT_VAL,
        CurriculumStage.STAGE6_RISK_DISCIPLINE,
        CurriculumStage.STAGE7_HOLDOUT_PROFILE,
    ]


def is_runway_stage(stage: CurriculumStage) -> bool:
    return stage in ordered_runway_stages()


def is_core_curriculum_stage(stage: CurriculumStage) -> bool:
    return stage in {
        CurriculumStage.STAGE1_TREND,
        CurriculumStage.STAGE2_RANGE,
        CurriculumStage.STAGE3_MIXED,
        CurriculumStage.STAGE4_VIABLE_PLANT,
        CurriculumStage.STAGE5_PROBE_HANDOFF,
    }
