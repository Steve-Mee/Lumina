"""Thin compatibility façade for stage-loop recovery symbol names.

Production ownership lives in:
- ``stage_loop_recovery_mixin`` (composite)
- ``stage_loop_recovery_terminal`` / ``_remediation`` / ``_adaptation``

This module keeps the historical helper names importable for docs/tests without
hosting plateau/terminal stub glue (removed; those paths are mixin-owned).
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.stage_loop_context import StageLoopContext

__all__ = [
    "adaptation_failure_key",
    "build_adaptation_recovery_context",
    "force_never_stop_recovery",
    "try_adaptation_stuck_escape",
    "try_adaptive_stall_recovery",
]


def adaptation_failure_key(stage: CurriculumStage) -> str:
    return {
        CurriculumStage.STAGE1_TREND: "stage1_winrate",
        CurriculumStage.STAGE2_RANGE: "stage2_metric",
        CurriculumStage.STAGE3_MIXED: "stage3_constitution",
    }.get(stage, "stage_metrics")


def build_adaptation_recovery_context(
    *,
    ctx: StageLoopContext,
    stage: CurriculumStage,
    failure_key: str,
    trigger_type: str,
    cur_cfg: Any,
    host: Any,
    stage_wins: int,
    stage_trades: int,
    patterns_mined: int,
    required: int,
    allow_provisional: bool,
    gen0_provisional: bool,
    escalation_level: int,
    attempt: int,
    plateau_active: bool,
    remediation_active: bool,
    remediation_step: int,
    remediation_cycle: int,
    autonomy_metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build kwargs for bus.adaptation_try_recovery (compat helper)."""
    del cur_cfg  # reserved for callers that mirror mixin context shape
    return {
        "failure_key": failure_key,
        "trigger_type": trigger_type,
        "stage_trades": stage_trades,
        "stage_wins": stage_wins,
        "patterns_mined": patterns_mined,
        "required_trades": required,
        "allow_provisional": allow_provisional,
        "gen0_provisional": gen0_provisional,
        "escalation_level": escalation_level,
        "attempt": attempt,
        "plateau_active": plateau_active,
        "remediation_active": remediation_active,
        "remediation_step": remediation_step,
        "remediation_cycle": remediation_cycle,
        "trade_budget_remaining": ctx.trade_budget_remaining(host),
        "adaptation_tier": ctx.adaptation_tier,
        "retries_this_stage": ctx.retries_this_stage,
        "autonomy_metrics": autonomy_metrics,
        "curriculum_stage": stage.value,
    }


def try_adaptive_stall_recovery(**kwargs: Any) -> bool:
    """Compat no-op: live path is ``StageLoopRecoveryAdaptationMixin``."""
    del kwargs
    return False


def force_never_stop_recovery(**kwargs: Any) -> bool:
    """Compat no-op: live path is ``StageLoopRecoveryAdaptationMixin``."""
    del kwargs
    return False


def try_adaptation_stuck_escape(**kwargs: Any) -> bool:
    """Compat no-op: live path is ``StageLoopRecoveryAdaptationMixin``."""
    del kwargs
    return False
