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

from lumina_core.birth.foundation_metrics import FOUNDATION_STAGE_COUNT


CURRICULUM_STAGE_COUNT = FOUNDATION_STAGE_COUNT


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
    from lumina_core.birth.foundation_stages import foundation_index_for_stage

    return foundation_index_for_stage(stage)


def runway_curriculum_total() -> int:
    """Birth HUD is always 5. Legacy runway is post-Birth, not this counter."""
    return FOUNDATION_STAGE_COUNT


def stage_display_name(stage: CurriculumStage) -> str:
    from lumina_core.birth.foundation_stages import foundation_display_name

    return foundation_display_name(stage)


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
        return PassCriteria(
            id="closed_loop",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric="median loss R ≤ 1.5 · settlement ≥70% · entropy alive · net RR ≥ 0.80",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Median loss R",
            metric_max=1.5,
        )
    if stage == CurriculumStage.STAGE2_RANGE:
        return PassCriteria(
            id="selectivity",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric="occupancy 30–70% · median loss R ≤ 1.5 · round-trips · settlement",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Occupancy",
            metric_min=0.30,
            metric_max=0.70,
        )
    if stage == CurriculumStage.STAGE3_MIXED:
        return PassCriteria(
            id="mixed_regimes",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric="occupancy 25–75% · edge ≥ −5pp vs first-touch · median loss R ≤ 1.5",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Edge vs first-touch",
            metric_min=-0.05,
        )
    if stage == CurriculumStage.STAGE4_VIABLE_PLANT:
        return PassCriteria(
            id="viable_plant",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric="skill WR ≥ first-touch AND mean R ≥ E_mech−0.10 · occupancy 25–75%",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="Edge vs first-touch",
            metric_min=0.0,
        )
    if stage == CurriculumStage.STAGE5_PROBE_HANDOFF:
        return PassCriteria(
            id="probe_handoff",
            label=_pass_gate_label(
                pass_gate=required,
                training_budget=training_budget,
                metric="holdout edge ≥ −3pp · Sharpe > −2 · DD ≤ 25% · fitness vector",
            ),
            target_trades=required,
            training_budget_trades=training_budget,
            metric_label="OOS edge",
            metric_min=-0.03,
        )
    return PassCriteria(
        id="not_foundation",
        label="Not a Birth Foundation stage",
        target_trades=0,
        metric_label="Rejected",
        metric_target=None,
    )


def human_sub_phase(phase: str) -> str:
    mapping = {
        "curriculum_research": "Oracle research",
        "curriculum_learning": "Policy rollouts",
        "data_expansion": "Data expansion",
        "ppo_training": "PPO batch training",
        "post_birth_certificate": "Post-Birth certificate (Proving Ground)",
        "runway_stage": "Post-Birth certificate (Proving Ground)",
        "ppo_polish": "Post-Birth PPO polish",
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
