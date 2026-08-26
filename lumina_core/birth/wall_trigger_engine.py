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
    policy_entropy: float | None = None,
    ppo_steps: int = 0,
    policy_trades: int | None = None,
    policy_wins: int | None = None,
    plant_trades: int | None = None,
    plant_wins: int | None = None,
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
            policy_entropy=policy_entropy,
            ppo_steps=int(ppo_steps),
            policy_trades=policy_trades,
            policy_wins=policy_wins,
            plant_trades=plant_trades,
            plant_wins=plant_wins,
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
        policy_entropy=policy_entropy,
        ppo_steps=int(ppo_steps),
        policy_trades=policy_trades,
        policy_wins=policy_wins,
        plant_trades=plant_trades,
        plant_wins=plant_wins,
    )
    if not blocker_metric:
        return WallTriggerResult(triggered=False)

    if not force:
        # Starship honesty: wall budget exhausted + skill blocker → stall without
        # fragile 1pp stagnation counter (WR wobble was silencing runbook §6).
        if wall_budget_exhausted:
            trigger_type = "certified_stall"
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
        if elapsed_stage_sec < stall_wall:
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
        pending={
            "failure_key": "velocity_stall",
            "blocker_metric": "velocity_stall",
            "blocker_value": float(low_velocity_attempts),
            "blocker_reason": "velocity_stall",
        },
    )


def evaluate_adaptation_stuck(
    *,
    stage_trades: int,
    last_adaptation_stage_trades: int,
    trades_beyond_hard_stop: bool,
    rollouts_since_last_adaptation: int = 0,
    min_rollouts_since_adaptation: int = 5,
) -> WallTriggerResult:
    """True only after adaptation left trade-count frozen *and* N train laps ran.

    Raptor v10: without the rollout debounce, every adapt at trades=T immediately
    re-fires stuck on the next loop top (before rollouts) → death spiral.
    """
    if not trades_beyond_hard_stop or stage_trades < 1:
        return WallTriggerResult(triggered=False)
    if last_adaptation_stage_trades != stage_trades:
        return WallTriggerResult(triggered=False)
    min_r = max(0, int(min_rollouts_since_adaptation))
    if int(rollouts_since_last_adaptation) < min_r:
        return WallTriggerResult(triggered=False)
    return WallTriggerResult(
        triggered=True,
        trigger_type="adaptation_stuck",
        failure_key="adaptation_stuck",
        pending={
            "failure_key": "adaptation_stuck",
            "blocker_metric": "adaptation_stuck",
            "blocker_value": float(stage_trades),
            "blocker_reason": "adaptation_loop_blocked",
            "rollouts_since_last_adaptation": int(rollouts_since_last_adaptation),
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
    rollouts_since_last_adaptation: int = 0,
    policy_entropy: float | None = None,
    ppo_steps: int = 0,
    policy_trades: int | None = None,
    policy_wins: int | None = None,
    plant_trades: int | None = None,
    plant_wins: int | None = None,
) -> WallTriggerResult:
    """Unified entry: adaptation stuck (debounced) then certified stall."""
    trades_beyond = evaluate_trades_beyond_gate(
        stage_trades=stage_trades,
        required=required,
        cfg=cfg,
    )
    min_rollouts = int(getattr(cfg, "adaptation_stuck_min_rollouts", 5) or 5)
    stuck = evaluate_adaptation_stuck(
        stage_trades=stage_trades,
        last_adaptation_stage_trades=last_adaptation_stage_trades,
        trades_beyond_hard_stop=trades_beyond and stage_trades >= required,
        rollouts_since_last_adaptation=int(rollouts_since_last_adaptation),
        min_rollouts_since_adaptation=max(1, min_rollouts),
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
        policy_entropy=policy_entropy,
        ppo_steps=int(ppo_steps),
        policy_trades=policy_trades,
        policy_wins=policy_wins,
        plant_trades=plant_trades,
        plant_wins=plant_wins,
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
