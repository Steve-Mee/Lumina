"""Pass criteria and curriculum stage display helpers for birth scorecards."""

from __future__ import annotations

from dataclasses import dataclass

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import (
    CurriculumStage,
    stage1_winrate_pass_threshold,
    stage_pass_trades,
    stage_trade_target,
)

CURRICULUM_STAGE_COUNT = 3


@dataclass(frozen=True, slots=True)
class PassCriteria:
    id: str
    label: str
    target_trades: int
    metric_label: str
    training_budget_trades: int = 0
    metric_target: float | None = None
    metric_min: float | None = None
    metric_max: float | None = None


def _pass_gate_label(*, pass_gate: int, training_budget: int, metric: str) -> str:
    if training_budget > pass_gate:
        return f">={pass_gate} pass gate ({training_budget} budget) · {metric}"
    return f">={pass_gate} · {metric}"


def curriculum_index_for_stage(stage: CurriculumStage) -> int:
    mapping = {
        CurriculumStage.STAGE1_TREND: 1,
        CurriculumStage.STAGE2_RANGE: 2,
        CurriculumStage.STAGE3_MIXED: 3,
        CurriculumStage.STAGE5_PROFIT_VAL: 5,
        CurriculumStage.STAGE6_RISK_DISCIPLINE: 6,
        CurriculumStage.STAGE7_HOLDOUT_PROFILE: 7,
        CurriculumStage.STAGE4_POLISH: 8,
    }
    return mapping.get(stage, 0)


def runway_curriculum_total() -> int:
    return 7


def stage_display_name(stage: CurriculumStage) -> str:
    names = {
        CurriculumStage.STAGE1_TREND: "Trend",
        CurriculumStage.STAGE2_RANGE: "Range patience",
        CurriculumStage.STAGE3_MIXED: "Mixed regimes",
        CurriculumStage.STAGE5_PROFIT_VAL: "Runway profit",
        CurriculumStage.STAGE6_RISK_DISCIPLINE: "Runway risk",
        CurriculumStage.STAGE7_HOLDOUT_PROFILE: "Runway generalize",
        CurriculumStage.STAGE4_POLISH: "Polish & certificate",
    }
    return names.get(stage, stage.value.replace("_", " ").title())


def pass_criteria_for_stage(
    stage: CurriculumStage,
    *,
    cfg: BirthCurriculumConfig | None = None,
    target_trades: int = 0,
) -> PassCriteria:
    if cfg is not None:
        required = stage_pass_trades(stage, cfg)
        training_budget = stage_trade_target(stage, cfg)
    else:
        training_budget = max(1, int(target_trades))
        required = max(50, min(100, training_budget))
    if stage == CurriculumStage.STAGE1_TREND:
        wr_gate = stage1_winrate_pass_threshold(cfg)
        edgescore_on = bool(getattr(cfg, "stage1_edgescore_enabled", False)) if cfg else False
        if edgescore_on:
            # Operator-facing label must match survival vs skill-side floors
            # (docs/birth-curriculum-stage-floors.md — locked doctrine).
            survival_on = bool(
                getattr(cfg, "birth_survival_pass_enabled", True) if cfg else True
            )
            if survival_on:
                hygiene = float(
                    getattr(cfg, "birth_survival_wr_floor", 0.20) if cfg else 0.20
                )
                exp_floor = float(
                    getattr(cfg, "birth_survival_expectancy_floor", -0.50)
                    if cfg
                    else -0.50
                )
                exp_txt = f"expectancy >= {exp_floor * 100.0:.0f}% (survival)"
                wr_label = "survival WR"
            else:
                hygiene = float(
                    getattr(cfg, "stage1_winrate_pass_floor", 0.35) if cfg else 0.35
                )
                exp_txt = "expectancy >= -15% (skill-side)"
                wr_label = "hygiene WR"
            return PassCriteria(
                id="trend_edgescore",
                label=_pass_gate_label(
                    pass_gate=required,
                    training_budget=training_budget,
                    metric=(
                        f"EdgeScore | {wr_label}>={hygiene:.0%} | hold band | "
                        f"entropy alive | {exp_txt} "
                        f"(WR {wr_gate:.0%} recommended)"
                    ),
                ),
                target_trades=required,
                training_budget_trades=training_budget,
                metric_label="EdgeScore",
                # Hygiene floor lives in the label; EdgeScore pass is composite (not score>=0.35).
                metric_target=None,
            )
        return PassCriteria(
            id="trend_winrate",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"winrate >={wr_gate:.0%}",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Winrate",
            metric_target=wr_gate,
        )
    if stage == CurriculumStage.STAGE2_RANGE:
        if bool(getattr(cfg, "stage2_edgescore_enabled", False)) if cfg else False:
            return PassCriteria(
                id="range_edgescore",
                label=_pass_gate_label(
                    pass_gate=required,
                    training_budget=training_budget,
                    metric=(
                        "EdgeScore | flat 30-70% | round-trips | "
                        "entropy alive | early-quality expectancy >= -15% "
                        "(not Stage-1 survival -50%)"
                    ),
                ),
                target_trades=required,
                training_budget_trades=training_budget,
                metric_label="EdgeScore",
                metric_min=0.30,
                metric_max=0.70,
            )
        return PassCriteria(
            id="range_roundtrip",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric="position-flat 30–70% on range ticks",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Position flat",
            metric_min=0.30,
            metric_max=0.70,
        )
    if stage == CurriculumStage.STAGE3_MIXED:
        wr_floor = float(getattr(cfg, "stage3_winrate_floor", 0.35) if cfg else 0.35)
        hold_cap = float(getattr(cfg, "stage3_hold_ratio_max", 0.70) if cfg else 0.70)
        if bool(getattr(cfg, "stage3_edgescore_enabled", False)) if cfg else False:
            return PassCriteria(
                id="mixed_edgescore",
                label=_pass_gate_label(
                    pass_gate=required,
                    training_budget=training_budget,
                    metric=(
                        f"EdgeScore | hygiene WR>={wr_floor:.0%} | hold<={hold_cap:.0%} | "
                        f"entropy alive | early-quality expectancy >= -15% "
                        f"(not Stage-1 survival -50%)"
                    ),
                ),
                target_trades=required,
                training_budget_trades=training_budget,
                metric_label="EdgeScore",
                metric_target=None,
                metric_max=hold_cap,
            )
        return PassCriteria(
            id="mixed_foundation",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"WR>={wr_floor:.0%} · hold≤{hold_cap:.0%} · 0 hard violations",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Mixed winrate",
            metric_target=wr_floor,
            metric_max=hold_cap,
        )
    if stage == CurriculumStage.STAGE5_PROFIT_VAL:
        wr = float(getattr(cfg, "runway_stage5_winrate_pass", 0.40) if cfg else 0.40)
        hold = float(getattr(cfg, "runway_stage5_hold_ratio_max", 0.55) if cfg else 0.55)
        return PassCriteria(
            id="runway_profit_val",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"val WR >={wr:.0%} · hold ≤{hold:.0%}",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Val winrate",
            metric_target=wr,
        )
    if stage == CurriculumStage.STAGE6_RISK_DISCIPLINE:
        sharpe = float(getattr(cfg, "runway_stage6_sharpe_min", 0.20) if cfg else 0.20)
        dd = float(getattr(cfg, "runway_stage6_drawdown_max_pct", 12.0) if cfg else 12.0)
        return PassCriteria(
            id="runway_risk",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"Sharpe >={sharpe:.2f} · DD ≤{dd:.0f}%",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Val Sharpe",
            metric_target=sharpe,
        )
    if stage == CurriculumStage.STAGE7_HOLDOUT_PROFILE:
        wr = float(getattr(cfg, "runway_stage7_winrate_min", 0.45) if cfg else 0.45)
        return PassCriteria(
            id="runway_holdout_profile",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric=f"profile WR >={wr:.0%} · EP OOS probe",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Profile winrate",
            metric_target=wr,
        )
    return PassCriteria(
        id="polish_complete",
        label="Final PPO buffer polish",
        target_trades=0,
        metric_label="Polish",
        metric_target=None,
    )


def human_sub_phase(phase: str) -> str:
    mapping = {
        "curriculum_research": "Oracle research",
        "curriculum_learning": "Policy rollouts",
        "data_expansion": "Data expansion",
        "ppo_training": "PPO batch training",
        "ppo_polish": "Final PPO polish",
        "oos_evaluation": "OOS certificate eval",
        "parallel_simulation": "Parallel simulation",
    }
    key = str(phase or "").strip().lower()
    return mapping.get(key, key.replace("_", " ").title() if key else "In progress")


def compute_advancing(
    *,
    stage_trades: int,
    patterns_mined: int,
    prev_stage_trades: int,
    prev_patterns_mined: int,
    elapsed_since_snapshot_sec: float,
    stale_after_sec: float = 120.0,
) -> bool:
    has_delta = stage_trades > prev_stage_trades or patterns_mined > prev_patterns_mined
    return bool(has_delta)


def parse_curriculum_stage(value: str) -> CurriculumStage | None:
    raw = str(value or "").strip().lower()
    for stage in CurriculumStage:
        if stage.value == raw:
            return stage
    return None


def learning_metric_target(
    stage: CurriculumStage,
    *,
    cfg: BirthCurriculumConfig | None = None,
    pass_criteria: PassCriteria | None = None,
) -> float:
    """Winrate target for hold-trap / plateau recovery (not stage pass gates)."""
    if stage == CurriculumStage.STAGE1_TREND:
        return stage1_winrate_pass_threshold(cfg)
    if stage == CurriculumStage.STAGE3_MIXED:
        return float(getattr(cfg, "stage1_winrate_recommended", 0.45) if cfg is not None else 0.45)
    if pass_criteria is not None and pass_criteria.metric_target is not None:
        return float(pass_criteria.metric_target)
    return 0.45
