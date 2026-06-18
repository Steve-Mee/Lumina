"""Birth curriculum stage scorecard helpers for UI transparency."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, stage_pass_trades

CURRICULUM_STAGE_COUNT = 3

SCORECARD_PRESERVE_KEYS: tuple[str, ...] = (
    "curriculum_stage",
    "stage_trades",
    "stage_target_trades",
    "stage_wins",
    "stage_winrate",
    "stage_hold_ratio",
    "stage_hold_signals",
    "stage_total_signals",
    "curriculum_index",
    "curriculum_total",
    "stages_passed",
    "pass_criteria_id",
    "pass_criteria_label",
    "pass_metric_label",
    "pass_metric_target",
    "pass_metric_min",
    "pass_metric_max",
    "stage_display_name",
    "sub_phase",
    "sub_phase_label",
    "constitution_violations",
    "is_advancing",
    "patterns_mined",
    "learning_attempt",
    "exploration_active",
    "oracle_wins",
    "escalation_level",
    "gen0_provisional",
    "data_days_loaded",
    "expansion_step",
    "stage_range_hold_signals",
    "stage_range_total_signals",
    "stage_range_flat_bars",
    "stage_range_round_trips",
    "stage_range_flat_ratio",
    "stage_wall_remaining_sec",
    "stage_blocker_metric",
    "stage_blocker_value",
    "pass_reason",
    "provisional_pass",
)


@dataclass(frozen=True, slots=True)
class PassCriteria:
    id: str
    label: str
    target_trades: int
    metric_label: str
    metric_target: float | None = None
    metric_min: float | None = None
    metric_max: float | None = None


def curriculum_index_for_stage(stage: CurriculumStage) -> int:
    if stage == CurriculumStage.STAGE1_TREND:
        return 1
    if stage == CurriculumStage.STAGE2_RANGE:
        return 2
    if stage == CurriculumStage.STAGE3_MIXED:
        return 3
    if stage == CurriculumStage.STAGE4_POLISH:
        return 4
    return 0


def stage_display_name(stage: CurriculumStage) -> str:
    names = {
        CurriculumStage.STAGE1_TREND: "Trend",
        CurriculumStage.STAGE2_RANGE: "Range patience",
        CurriculumStage.STAGE3_MIXED: "Mixed regimes",
        CurriculumStage.STAGE4_POLISH: "PPO polish",
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
    else:
        required = max(50, min(100, max(1, int(target_trades))))
    if stage == CurriculumStage.STAGE1_TREND:
        return PassCriteria(
            id="trend_winrate",
            label=f">={required} trades · winrate >=45%",
            target_trades=required,
            metric_label="Winrate",
            metric_target=0.45,
        )
    if stage == CurriculumStage.STAGE2_RANGE:
        return PassCriteria(
            id="range_roundtrip",
            label=f">={required} trades · position-flat 30–70% on range ticks",
            target_trades=required,
            metric_label="Position flat",
            metric_min=0.30,
            metric_max=0.70,
        )
    if stage == CurriculumStage.STAGE3_MIXED:
        return PassCriteria(
            id="mixed_constitution",
            label=f">={required} trades · 0 constitution violations",
            target_trades=required,
            metric_label="Violations",
            metric_target=0.0,
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
    if has_delta:
        return True
    return elapsed_since_snapshot_sec <= stale_after_sec


def parse_curriculum_stage(value: str) -> CurriculumStage | None:
    raw = str(value or "").strip().lower()
    for stage in CurriculumStage:
        if stage.value == raw:
            return stage
    return None


def enrich_progress_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure scorecard fields exist and winrate is recomputed from stage wins/trades."""
    merged = dict(payload)
    stage = parse_curriculum_stage(str(merged.get("curriculum_stage", "") or ""))
    if stage is None:
        return merged

    stage_trades = max(0, int(merged.get("stage_trades", 0) or 0))
    if merged.get("stage_wins") is not None:
        stage_wins = max(0, int(merged.get("stage_wins", 0) or 0))
        merged["stage_wins"] = stage_wins
        if stage_trades > 0:
            merged["stage_winrate"] = round(float(stage_wins) / float(stage_trades), 4)

    stage_target = int(merged.get("stage_target_trades", 0) or 0)
    budget_target = max(stage_target, 100)
    if not merged.get("pass_criteria_id"):
        criteria = pass_criteria_for_stage(stage, target_trades=budget_target)
        merged.setdefault("pass_criteria_id", criteria.id)
        merged.setdefault("pass_criteria_label", criteria.label)
        merged.setdefault("pass_metric_label", criteria.metric_label)
        merged.setdefault("pass_metric_target", criteria.metric_target)
        merged.setdefault("pass_metric_min", criteria.metric_min)
        merged.setdefault("pass_metric_max", criteria.metric_max)
        merged.setdefault("stage_display_name", stage_display_name(stage))
    if not merged.get("curriculum_index"):
        merged["curriculum_index"] = curriculum_index_for_stage(stage)
    merged.setdefault("curriculum_total", CURRICULUM_STAGE_COUNT)

    phase = str(merged.get("sub_phase") or merged.get("phase") or "").strip().lower()
    if phase:
        merged.setdefault("sub_phase", phase)
        merged.setdefault("sub_phase_label", human_sub_phase(phase))
    return merged


def compute_stage_blocker(
    stage: CurriculumStage,
    *,
    stage_trades: int,
    stage_wins: int,
    hold_ratio: float,
    required: int,
    constitution_violations: int,
    range_flat_ratio: float,
    range_round_trips: int,
    range_total_signals: int,
) -> tuple[str | None, float | None, str | None]:
    """Return (blocker_metric_id, blocker_value, human pass/block reason)."""
    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    if stage == CurriculumStage.STAGE1_TREND:
        if trades < required:
            return (None, None, None)
        winrate = float(wins) / float(max(1, trades))
        if winrate < 0.45:
            return ("winrate", round(winrate, 4), f"winrate {winrate:.1%} < 45%")
        return (None, None, None)
    if stage == CurriculumStage.STAGE2_RANGE:
        if trades < required:
            return (None, None, None)
        if range_total_signals >= 50:
            metric = range_flat_ratio
            label = "position_flat"
            min_round_trips = max(3, required // 10)
            if range_round_trips < min_round_trips:
                return (
                    "round_trips",
                    float(range_round_trips),
                    f"round_trips {range_round_trips} < {min_round_trips}",
                )
        else:
            metric = hold_ratio
            label = "hold"
        if metric < 0.30 or metric > 0.70:
            return (label, round(metric, 4), f"{label} {metric:.1%} outside 30–70%")
        return (None, None, None)
    if stage == CurriculumStage.STAGE3_MIXED:
        if trades < required:
            return (None, None, None)
        if constitution_violations > 0:
            return (
                "constitution_violations",
                float(constitution_violations),
                f"violations {constitution_violations} > 0",
            )
        return (None, None, None)
    return (None, None, None)


def build_scorecard_payload(
    *,
    stage: CurriculumStage,
    curriculum_index: int,
    stages_passed: list[str],
    stage_trades: int,
    stage_wins: int,
    stage_hold_signals: int,
    stage_total_signals: int,
    constitution_violations: int,
    target_trades: int,
    phase: str,
    patterns_mined: int,
    learning_attempt: int,
    prev_stage_trades: int = 0,
    prev_patterns_mined: int = 0,
    snapshot_elapsed_sec: float = 0.0,
    stage_range_flat_bars: int = 0,
    stage_range_total_signals: int = 0,
    stage_range_round_trips: int = 0,
    provisional_pass: bool = False,
    cfg: BirthCurriculumConfig | None = None,
) -> dict[str, Any]:
    criteria = pass_criteria_for_stage(stage, cfg=cfg, target_trades=target_trades)
    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    hold_ratio = float(stage_hold_signals) / float(max(1, stage_total_signals))
    winrate = float(wins) / float(max(1, trades))
    is_advancing = compute_advancing(
        stage_trades=trades,
        patterns_mined=int(patterns_mined),
        prev_stage_trades=int(prev_stage_trades),
        prev_patterns_mined=int(prev_patterns_mined),
        elapsed_since_snapshot_sec=float(snapshot_elapsed_sec),
    )
    required = stage_pass_trades(stage, cfg) if cfg is not None else criteria.target_trades
    range_flat_ratio = float(stage_range_flat_bars) / float(max(1, stage_range_total_signals))
    blocker_metric, blocker_value, pass_reason = compute_stage_blocker(
        stage,
        stage_trades=trades,
        stage_wins=wins,
        hold_ratio=hold_ratio,
        required=required,
        constitution_violations=int(constitution_violations),
        range_flat_ratio=range_flat_ratio,
        range_round_trips=int(stage_range_round_trips),
        range_total_signals=int(stage_range_total_signals),
    )
    payload: dict[str, Any] = {
        "stage_wins": wins,
        "stage_winrate": round(winrate, 4),
        "stage_hold_ratio": round(hold_ratio, 4),
        "curriculum_index": int(curriculum_index),
        "curriculum_total": CURRICULUM_STAGE_COUNT,
        "stages_passed": list(stages_passed),
        "pass_criteria_id": criteria.id,
        "pass_criteria_label": criteria.label,
        "pass_metric_label": criteria.metric_label,
        "pass_metric_target": criteria.metric_target,
        "pass_metric_min": criteria.metric_min,
        "pass_metric_max": criteria.metric_max,
        "stage_display_name": stage_display_name(stage),
        "sub_phase": str(phase).strip().lower(),
        "sub_phase_label": human_sub_phase(phase),
        "constitution_violations": int(constitution_violations),
        "is_advancing": bool(is_advancing),
        "stage_target_trades": int(required),
    }
    if blocker_metric:
        payload["stage_blocker_metric"] = blocker_metric
        payload["stage_blocker_value"] = blocker_value
    if pass_reason:
        payload["pass_reason"] = pass_reason
    if provisional_pass:
        payload["provisional_pass"] = True
    return payload
