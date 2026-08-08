"""Pure helpers for stage-loop iteration (no control flow)."""
from __future__ import annotations

from typing import Any, Literal

from lumina_core.birth.curriculum import CurriculumStage

LoopAction = Literal["continue", "return", "fallthrough", "exit_stage"]


def failure_key_for_stage(stage: CurriculumStage) -> str:
    """Map curriculum stage to stall failure_key used in wall/plateau logic."""
    return {
        CurriculumStage.STAGE1_TREND: "stage1_winrate",
        CurriculumStage.STAGE2_RANGE: "stage2_metric",
        # Raptor v9: stage3 is foundation floors (WR/hold), not constitution-only.
        CurriculumStage.STAGE3_MIXED: "stage3_foundation",
    }.get(stage, "stage_metrics")


def force_failure_key_for_stage(stage: CurriculumStage) -> str:
    """Failure keys used when max-rollouts force-stall certified stages."""
    return {
        CurriculumStage.STAGE1_TREND: "stage1_winrate",
        CurriculumStage.STAGE2_RANGE: "stage2_metric",
        CurriculumStage.STAGE3_MIXED: "stage3_constitution",
    }.get(stage, "stage_metrics")


def history_unavailable_result(
    *,
    total_trades: int,
    ppo_steps: int,
    training_mode: str = "certified",
) -> dict[str, Any]:
    return {
        "status": "history_unavailable",
        "total_trades": int(total_trades),
        "ppo_steps": int(ppo_steps),
        "training_mode": training_mode,
    }


def stage_pass_event_data(
    *,
    stage_value: str,
    trades: int,
    wins: int,
    required: int,
    winrate: float,
    patterns_mined: int,
    attempts: int,
    pass_reason: str,
    provisional: bool,
) -> dict[str, Any]:
    return {
        "stage": stage_value,
        "trades": int(trades),
        "wins": int(wins),
        "required": int(required),
        "winrate": round(float(winrate), 4),
        "patterns_mined": int(patterns_mined),
        "attempts": int(attempts),
        "pass_reason": str(pass_reason),
        "provisional": bool(provisional),
    }


def stage_winrate(wins: int, trades: int) -> float:
    return float(wins) / float(max(1, int(trades)))


def wall_budget_elapsed(elapsed_stage_sec: float, max_stage_wall_sec: int) -> bool:
    return float(elapsed_stage_sec) >= max(300, int(max_stage_wall_sec))
