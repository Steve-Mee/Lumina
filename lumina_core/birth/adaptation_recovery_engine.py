"""Pure adaptation recovery decision logic for wall adaptation handler."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.adaptive_parameter_manager import (
    AdaptiveParameterPatch,
    WallAdaptationState,
    compute_parameter_patch,
)
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.meta_controller import (
    AdaptationDecision,
    LearningHealth,
    MetaActionPlan,
    get_adaptation_decision,
)
from lumina_core.birth.plateau_escalator import adaptation_stuck_escape_allowed


@dataclass(frozen=True, slots=True)
class AdaptationApplyResult:
    applied: bool
    recovery_kind: str = ""
    decision: AdaptationDecision | None = None
    dispatch: str = "continue_loop"
    parameter_patch: AdaptiveParameterPatch | None = None
    mine: bool = False
    mine_aggressive: bool = False
    expand_data: bool = False
    spawn_plateau: bool = False
    spawn_phoenix_reset: bool = False
    state_delta: dict[str, Any] = field(default_factory=dict)
    log_message: str = ""


def resolve_meta_adaptation_decision(
    adapt_plan: MetaActionPlan,
    *,
    adaptation_tier: int,
    retries_this_stage: int,
    exploration_chunk_size: int,
    rollout_chunk_trades: int,
    original_rollout_chunk: int,
) -> AdaptationDecision | None:
    decision = adapt_plan.adaptation
    if decision is not None and decision.should_retry:
        return decision
    if adaptation_tier == 0 and retries_this_stage == 0:
        return AdaptationDecision(
            should_retry=True,
            reason="stall_escalation",
            new_chunk_target=max(
                exploration_chunk_size,
                min(rollout_chunk_trades * 2, original_rollout_chunk),
            ),
            escalation_increase=1,
            log_message="Escalation ladder: forced recovery at stall boundary",
        )
    if adaptation_tier >= 1:
        return AdaptationDecision(
            should_retry=True,
            reason="persistent_recovery",
            new_chunk_target=max(exploration_chunk_size, rollout_chunk_trades),
            escalation_increase=0,
            log_message=(
                f"Persistent recovery tier {adaptation_tier + 1}"
            ),
        )
    return None


def resolve_legacy_adaptation_decision(
    *,
    stage_trades: int,
    required: int,
    winrate: float,
    winrate_history: list[float],
    escalation_level: int,
    adaptation_tier: int,
    retries_this_stage: int,
    exploration_chunk_size: int,
    rollout_chunk_trades: int,
    original_rollout_chunk: int,
    cfg: BirthCurriculumConfig,
) -> AdaptationDecision | None:
    decision = get_adaptation_decision(
        stage_trades=stage_trades,
        required=required,
        winrate=winrate,
        winrate_history=winrate_history,
        escalation_level=escalation_level,
        cfg=cfg,
    )
    if not decision.should_retry and adaptation_tier == 0 and retries_this_stage == 0:
        return AdaptationDecision(
            should_retry=True,
            reason="stall_escalation",
            new_chunk_target=max(
                exploration_chunk_size,
                min(rollout_chunk_trades * 2, original_rollout_chunk),
            ),
            escalation_increase=1,
            log_message="Escalation ladder: forced recovery at stall boundary",
        )
    if not decision.should_retry and adaptation_tier >= 1:
        return AdaptationDecision(
            should_retry=True,
            reason="persistent_recovery",
            new_chunk_target=max(exploration_chunk_size, rollout_chunk_trades),
            escalation_increase=0,
            log_message=f"Persistent recovery tier {adaptation_tier + 1}",
        )
    if not decision.should_retry:
        return None
    return decision


def apply_adaptation_to_state(
    state: WallAdaptationState,
    decision: AdaptationDecision,
    *,
    failure_key: str,
    current_winrate: float,
    stage_trades: int,
    max_escalation_level: int,
    max_adaptation_tiers: int,
    max_stage_retries: int,
    exploration_chunk_size: int,
    original_rollout_chunk: int,
) -> tuple[WallAdaptationState, int]:
    """Return updated state and effective chunk_target."""
    tier = state.adaptation_tier
    escalation = state.escalation_level
    retries = state.retries_this_stage

    if tier >= max_adaptation_tiers - 1:
        escalation = min(max_escalation_level, max_escalation_level)
        chunk = max(exploration_chunk_size, original_rollout_chunk)
    else:
        escalation = min(max_escalation_level, escalation + decision.escalation_increase)
        chunk = decision.new_chunk_target

    history = list(state.adaptation_history)
    history.append(
        {
            "timestamp": time.time(),
            "reason": decision.reason,
            "chunk_target": chunk,
            "escalation": escalation,
            "tier": tier,
            "winrate": current_winrate,
            "failure_key": failure_key,
        }
    )
    retries += 1
    if retries >= max_stage_retries:
        if tier + 1 < max_adaptation_tiers:
            tier += 1
            retries = 0
        else:
            retries = 0

    state.adaptation_tier = tier
    state.escalation_level = escalation
    state.retries_this_stage = retries
    state.adaptation_history = history
    state.last_adaptation_stage_trades = int(stage_trades)
    state.recovery_attempts += 1
    state.recovery_successes += 1
    return state, chunk


def plan_adaptive_recovery(
    *,
    cfg: BirthCurriculumConfig,
    state: WallAdaptationState,
    failure_key: str,
    trigger_type: str,
    stage_trades: int,
    required: int,
    current_winrate: float,
    winrate_history: list[float],
    original_rollout_chunk: int,
    rollout_chunk_trades: int,
    trade_budget_remaining: int,
    terminal_blocked: bool,
    constitution_blocked: bool,
    meta_plan: MetaActionPlan | None = None,
    learning_health: LearningHealth | str = LearningHealth.FLAT,
) -> AdaptationApplyResult:
    if not cfg.adaptation_enabled or cfg.wall_behavior != "adaptive":
        return AdaptationApplyResult(applied=False, dispatch="terminal_notify_only")
    if constitution_blocked:
        return AdaptationApplyResult(applied=False, dispatch="terminal_notify_only")
    if terminal_blocked:
        return AdaptationApplyResult(applied=False, dispatch="terminal_notify_only")

    if trigger_type == "adaptation_stuck":
        if not adaptation_stuck_escape_allowed(
            escapes_used=state.adaptation_stuck_escapes,
            max_escapes=cfg.max_adaptation_stuck_escapes,
            trade_budget_remaining=trade_budget_remaining,
        ):
            return AdaptationApplyResult(applied=False)
        decision = AdaptationDecision(
            should_retry=True,
            reason="adaptation_stuck_escape",
            new_chunk_target=max(
                cfg.exploration_chunk_size,
                min(original_rollout_chunk * 2, rollout_chunk_trades * 2),
            ),
            escalation_increase=2,
            log_message="Adaptation stuck escape: phoenix reset + forced recovery",
        )
        return AdaptationApplyResult(
            applied=True,
            recovery_kind="stuck_escape",
            decision=decision,
            dispatch="continue_loop",
            mine=True,
            mine_aggressive=True,
            expand_data=cfg.auto_expand_on_adaptation and state.adaptation_tier >= 1,
            spawn_plateau=True,
            spawn_phoenix_reset=True,
            state_delta={"adaptation_stuck_escapes": state.adaptation_stuck_escapes + 1},
        )

    decision: AdaptationDecision | None = None
    mine = False
    mine_aggressive = False
    expand_data = False

    if meta_plan is not None:
        decision = resolve_meta_adaptation_decision(
            meta_plan,
            adaptation_tier=state.adaptation_tier,
            retries_this_stage=state.retries_this_stage,
            exploration_chunk_size=cfg.exploration_chunk_size,
            rollout_chunk_trades=rollout_chunk_trades,
            original_rollout_chunk=original_rollout_chunk,
        )
        if decision is None:
            return AdaptationApplyResult(applied=False)
        mine = meta_plan.mine
        mine_aggressive = meta_plan.mine_aggressive
        expand_data = meta_plan.expand_data
    else:
        decision = resolve_legacy_adaptation_decision(
            stage_trades=stage_trades,
            required=required,
            winrate=current_winrate,
            winrate_history=winrate_history,
            escalation_level=state.escalation_level,
            adaptation_tier=state.adaptation_tier,
            retries_this_stage=state.retries_this_stage,
            exploration_chunk_size=cfg.exploration_chunk_size,
            rollout_chunk_trades=rollout_chunk_trades,
            original_rollout_chunk=original_rollout_chunk,
            cfg=cfg,
        )
        if decision is None:
            return AdaptationApplyResult(applied=False)
        if state.adaptation_tier >= 1:
            mine = True
        if state.adaptation_tier >= 2 and cfg.auto_expand_on_adaptation:
            expand_data = True

    patch = compute_parameter_patch(
        learning_health=learning_health,
        current_winrate_window=state.effective_winrate_window,
        current_reward_window=state.effective_reward_window,
        cfg=cfg,
        adaptation_tier=state.adaptation_tier,
        post_volume_gate=stage_trades >= required,
    )

    return AdaptationApplyResult(
        applied=True,
        recovery_kind="adaptive",
        decision=decision,
        dispatch="continue_loop",
        parameter_patch=patch,
        mine=mine,
        mine_aggressive=mine_aggressive,
        expand_data=expand_data,
        log_message=decision.log_message,
    )


def plan_never_stop_recovery(
    *,
    cfg: BirthCurriculumConfig,
    state: WallAdaptationState,
    failure_key: str,
    rollout_chunk_trades: int,
    terminal_blocked: bool,
) -> AdaptationApplyResult:
    if not cfg.adaptation_enabled or cfg.wall_behavior != "adaptive":
        return AdaptationApplyResult(applied=False)
    if terminal_blocked:
        return AdaptationApplyResult(applied=False)

    decision = AdaptationDecision(
        should_retry=True,
        reason="never_stop_forced",
        new_chunk_target=max(cfg.exploration_chunk_size, rollout_chunk_trades),
        escalation_increase=1 if state.adaptation_tier == 0 else 0,
        log_message="Never-stop: forcing adaptive recovery instead of terminal stall",
    )
    return AdaptationApplyResult(
        applied=True,
        recovery_kind="never_stop",
        decision=decision,
        dispatch="continue_loop",
        mine=state.adaptation_tier >= 1,
        expand_data=state.adaptation_tier >= 2 and cfg.auto_expand_on_adaptation,
    )


__all__ = [
    "AdaptationApplyResult",
    "apply_adaptation_to_state",
    "plan_adaptive_recovery",
    "plan_never_stop_recovery",
    "resolve_legacy_adaptation_decision",
    "resolve_meta_adaptation_decision",
]
