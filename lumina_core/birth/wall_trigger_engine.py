"""Pure wall/event trigger evaluation for birth certified stage stalls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage, graduation_requires_clean_constitution
from lumina_core.birth.plateau_escalator import should_trades_beyond_gate_hard_stop
from lumina_core.birth.stage_scorecard import compute_stage_blocker


@dataclass(frozen=True, slots=True)
class WallTriggerResult:
    triggered: bool
    trigger_type: str = ""
    failure_key: str = ""
    pending: dict[str, Any] = field(default_factory=dict)
    constitution_blocked: bool = False


def constitution_blocks_adaptation(
    *,
    stage: CurriculumStage,
    constitution_violations: int,
) -> bool:
    """Stages 1–3 require zero constitution violations before adaptation."""
    return graduation_requires_clean_constitution(stage) and constitution_violations > 0


def evaluate_certified_stall(
    *,
    stage: CurriculumStage,
    stage_trades: int,
    stage_wins: int,
    required: int,
    hold_ratio: float,
    constitution_violations: int,
    range_flat_ratio: float,
    range_round_trips: int,
    range_total_signals: int,
    elapsed_stage_sec: float,
    winrate_stagnation_count: int,
    hold_stagnation_count: int,
    wall_budget_exhausted: bool,
    allow_provisional: bool,
    failure_key: str,
    force: bool,
    cfg: BirthCurriculumConfig,
) -> WallTriggerResult:
    """Evaluate certified stage stall (stagnation + wall time)."""
    if allow_provisional or stage_trades < required:
        return WallTriggerResult(triggered=False)

    blocked = constitution_blocks_adaptation(
        stage=stage,
        constitution_violations=constitution_violations,
    )
    if blocked and stage_trades >= required:
        blocker_metric, blocker_value, blocker_reason = compute_stage_blocker(
            stage,
            stage_trades=stage_trades,
            stage_wins=stage_wins,
            hold_ratio=hold_ratio,
            required=required,
            constitution_violations=constitution_violations,
            range_flat_ratio=range_flat_ratio,
            range_round_trips=range_round_trips,
            range_total_signals=range_total_signals,
            cfg=cfg,
        )
        pending = {
            "failure_key": failure_key,
            "blocker_metric": blocker_metric or "constitution_violations",
            "blocker_value": blocker_value if blocker_value is not None else float(constitution_violations),
            "blocker_reason": blocker_reason or f"violations {constitution_violations} > 0",
        }
        return WallTriggerResult(
            triggered=True,
            trigger_type="constitution_stall",
            failure_key=failure_key,
            pending=pending,
            constitution_blocked=True,
        )

    blocker_metric, blocker_value, blocker_reason = compute_stage_blocker(
        stage,
        stage_trades=stage_trades,
        stage_wins=stage_wins,
        hold_ratio=hold_ratio,
        required=required,
        constitution_violations=constitution_violations,
        range_flat_ratio=range_flat_ratio,
        range_round_trips=range_round_trips,
        range_total_signals=range_total_signals,
        cfg=cfg,
    )
    if not blocker_metric:
        return WallTriggerResult(triggered=False)

    if not force:
        stagnation_met = False
        if stage == CurriculumStage.STAGE1_TREND:
            stagnation_met = (
                winrate_stagnation_count >= cfg.stage1_winrate_stagnation_rollouts
            )
        elif stage == CurriculumStage.STAGE2_RANGE:
            stagnation_met = hold_stagnation_count >= cfg.stage2_hold_stagnation_rollouts
        elif stage == CurriculumStage.STAGE3_MIXED:
            stagnation_met = constitution_violations > 0
        stall_wall = max(300, int(cfg.certified_stage_stall_wall_sec))
        if not stagnation_met:
            return WallTriggerResult(triggered=False)
        if not (elapsed_stage_sec >= stall_wall or wall_budget_exhausted):
            return WallTriggerResult(triggered=False)

    trigger_type = "trades_beyond_gate" if force else "certified_stall"
    pending = {
        "failure_key": failure_key,
        "blocker_metric": blocker_metric,
        "blocker_value": blocker_value,
        "blocker_reason": blocker_reason,
    }
    blocked = constitution_blocks_adaptation(
        stage=stage,
        constitution_violations=constitution_violations,
    )
    return WallTriggerResult(
        triggered=True,
        trigger_type=trigger_type,
        failure_key=failure_key,
        pending=pending,
        constitution_blocked=blocked,
    )


def evaluate_velocity_stall(
    *,
    low_velocity_attempts: int,
    cfg: BirthCurriculumConfig,
) -> WallTriggerResult:
    threshold = int(cfg.velocity_stall_attempt_threshold)
    if low_velocity_attempts < threshold:
        return WallTriggerResult(triggered=False)
    return WallTriggerResult(
        triggered=True,
        trigger_type="velocity_stall",
        failure_key="velocity_stall",
        pending={"failure_key": "velocity_stall", "blocker_reason": "velocity_stall"},
    )


def evaluate_adaptation_stuck(
    *,
    stage_trades: int,
    last_adaptation_stage_trades: int,
    trades_beyond_hard_stop: bool,
) -> WallTriggerResult:
    if not trades_beyond_hard_stop or stage_trades < 1:
        return WallTriggerResult(triggered=False)
    if last_adaptation_stage_trades != stage_trades:
        return WallTriggerResult(triggered=False)
    return WallTriggerResult(
        triggered=True,
        trigger_type="adaptation_stuck",
        failure_key="adaptation_stuck",
        pending={
            "failure_key": "adaptation_stuck",
            "blocker_reason": "adaptation_loop_blocked",
        },
    )


def evaluate_trades_beyond_gate(
    *,
    stage_trades: int,
    required: int,
    cfg: BirthCurriculumConfig,
) -> bool:
    return should_trades_beyond_gate_hard_stop(stage_trades, required, cfg)


def evaluate_wall_trigger(
    *,
    stage: CurriculumStage,
    stage_trades: int,
    stage_wins: int,
    required: int,
    hold_ratio: float,
    constitution_violations: int,
    range_flat_ratio: float,
    range_round_trips: int,
    range_total_signals: int,
    elapsed_stage_sec: float,
    winrate_stagnation_count: int,
    hold_stagnation_count: int,
    wall_budget_exhausted: bool,
    allow_provisional: bool,
    failure_key: str,
    force: bool,
    low_velocity_attempts: int,
    last_adaptation_stage_trades: int,
    cfg: BirthCurriculumConfig,
) -> WallTriggerResult:
    """Unified entry: certified stall takes priority, then adaptation stuck."""
    trades_beyond = evaluate_trades_beyond_gate(
        stage_trades=stage_trades,
        required=required,
        cfg=cfg,
    )
    stuck = evaluate_adaptation_stuck(
        stage_trades=stage_trades,
        last_adaptation_stage_trades=last_adaptation_stage_trades,
        trades_beyond_hard_stop=trades_beyond and stage_trades >= required,
    )
    if stuck.triggered:
        return stuck

    return evaluate_certified_stall(
        stage=stage,
        stage_trades=stage_trades,
        stage_wins=stage_wins,
        required=required,
        hold_ratio=hold_ratio,
        constitution_violations=constitution_violations,
        range_flat_ratio=range_flat_ratio,
        range_round_trips=range_round_trips,
        range_total_signals=range_total_signals,
        elapsed_stage_sec=elapsed_stage_sec,
        winrate_stagnation_count=winrate_stagnation_count,
        hold_stagnation_count=hold_stagnation_count,
        wall_budget_exhausted=wall_budget_exhausted,
        allow_provisional=allow_provisional,
        failure_key=failure_key,
        force=force or (trades_beyond and stage_trades >= required),
        cfg=cfg,
    )


__all__ = [
    "WallTriggerResult",
    "constitution_blocks_adaptation",
    "evaluate_adaptation_stuck",
    "evaluate_certified_stall",
    "evaluate_trades_beyond_gate",
    "evaluate_velocity_stall",
    "evaluate_wall_trigger",
]
