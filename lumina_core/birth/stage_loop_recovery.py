"""Stage loop recovery helpers — stall/adaptation/plateau orchestration via BirthBusClient."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    adaptation_stuck_escape_allowed,
    can_force_never_stop_recovery,
)
from lumina_core.birth.stage_loop_context import StageLoopContext
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_recovery")


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
    """Build kwargs for bus.adaptation_try_recovery."""
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


def try_adaptive_stall_recovery(
    *,
    bus: BirthBusClient,
    ctx: StageLoopContext,
    stage: CurriculumStage,
    cur_cfg: Any,
    host: Any,
    failure_key: str,
    trigger_type: str,
    constitution_blocked: bool,
    apply_result: Any,
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
) -> bool:
    if constitution_blocked:
        return False
    context = build_adaptation_recovery_context(
        ctx=ctx,
        stage=stage,
        failure_key=failure_key,
        trigger_type=trigger_type,
        cur_cfg=cur_cfg,
        host=host,
        stage_wins=stage_wins,
        stage_trades=stage_trades,
        patterns_mined=patterns_mined,
        required=required,
        allow_provisional=allow_provisional,
        gen0_provisional=gen0_provisional,
        escalation_level=escalation_level,
        attempt=attempt,
        plateau_active=plateau_active,
        remediation_active=remediation_active,
        remediation_step=remediation_step,
        remediation_cycle=remediation_cycle,
        autonomy_metrics=autonomy_metrics,
    )
    result = bus.adaptation_try_recovery(stage, **context)
    return bool(apply_result(result))


def force_never_stop_recovery(
    *,
    bus: BirthBusClient,
    ctx: StageLoopContext,
    stage: CurriculumStage,
    cur_cfg: Any,
    host: Any,
    failure_key: str,
    apply_result: Any,
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
) -> bool:
    if not can_force_never_stop_recovery(cur_cfg=cur_cfg, trade_budget_remaining=ctx.trade_budget_remaining(host)):
        return False
    context = build_adaptation_recovery_context(
        ctx=ctx,
        stage=stage,
        failure_key=failure_key,
        trigger_type="never_stop",
        cur_cfg=cur_cfg,
        host=host,
        stage_wins=stage_wins,
        stage_trades=stage_trades,
        patterns_mined=patterns_mined,
        required=required,
        allow_provisional=allow_provisional,
        gen0_provisional=gen0_provisional,
        escalation_level=escalation_level,
        attempt=attempt,
        plateau_active=plateau_active,
        remediation_active=remediation_active,
        remediation_step=remediation_step,
        remediation_cycle=remediation_cycle,
        autonomy_metrics=autonomy_metrics,
    )
    result = bus.adaptation_try_recovery(stage, **context)
    return bool(apply_result(result))


def try_adaptation_stuck_escape(
    *,
    bus: BirthBusClient,
    ctx: StageLoopContext,
    stage: CurriculumStage,
    cur_cfg: Any,
    host: Any,
    failure_key: str,
    apply_result: Any,
    maybe_extend_budget: Any,
    stage_trades: int,
    stage_wins: int,
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
) -> bool:
    if not adaptation_stuck_escape_allowed(
        escapes_used=ctx.adaptation_stuck_escapes,
        max_escapes=cur_cfg.max_adaptation_stuck_escapes,
        trade_budget_remaining=ctx.trade_budget_remaining(host),
    ):
        return False
    logger.warning(
        "birth.adaptation.stuck_escape attempt=%s/%s trades=%s tier=%s failure=%s",
        ctx.adaptation_stuck_escapes + 1,
        cur_cfg.max_adaptation_stuck_escapes,
        stage_trades,
        ctx.adaptation_tier,
        failure_key,
    )
    maybe_extend_budget()
    context = build_adaptation_recovery_context(
        ctx=ctx,
        stage=stage,
        failure_key=failure_key,
        trigger_type="adaptation_stuck",
        cur_cfg=cur_cfg,
        host=host,
        stage_wins=stage_wins,
        stage_trades=stage_trades,
        patterns_mined=patterns_mined,
        required=required,
        allow_provisional=allow_provisional,
        gen0_provisional=gen0_provisional,
        escalation_level=escalation_level,
        attempt=attempt,
        plateau_active=plateau_active,
        remediation_active=remediation_active,
        remediation_step=remediation_step,
        remediation_cycle=remediation_cycle,
        autonomy_metrics=autonomy_metrics,
    )
    result = bus.adaptation_try_recovery(stage, **context)
    return bool(apply_result(result))


__all__ = [
    "adaptation_failure_key",
    "build_adaptation_recovery_context",
    "force_never_stop_recovery",
    "try_adaptation_stuck_escape",
    "try_adaptive_stall_recovery",
]