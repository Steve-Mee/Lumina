"""Post-rollout meta review and strong-recovery handling."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.meta_controller import (
    LearningHealth,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
)
from lumina_core.birth.meta_self_eval import SelfEvalPhase
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_rollout_post")


class StageLoopRolloutPostMixin(StageLoopMixinBase):
    """Meta observe/review/self-eval and strong-recovery after a sim rollout."""

    def _apply_post_rollout_meta(self, rollout: Any) -> None:
        snap: Any | None = None
        stall_result: StallDetectionResult | None = None
        if self.cur_cfg.meta_controller_enabled:
            self.bus.meta_patch_state(self.stage, increment_rollouts=True)
            snap, stall_result = self._observe_snapshot()
            if rollout.trades > 0:
                self.low_velocity_attempts = stall_result.low_velocity_attempts
            self_eval_skip_review = (
                self.cur_cfg.meta_self_eval_enabled
                and bool(self.bus.meta_self_eval_state(self.stage).get('active', False))
                and SelfEvalPhase(self.bus.meta_self_eval_state(self.stage).get('phase', 'idle'))
                in (SelfEvalPhase.PROBING, SelfEvalPhase.COMMITTED)
            )
            if self_eval_skip_review:
                complete_plan = self.bus.meta_on_probe_complete(self.stage, 
                    snap,
                    attempt=self.attempt + 1,
                )
                if complete_plan is not None:
                    self._apply_meta_plan(complete_plan, trigger="self_eval")
                    if complete_plan.suggest_provisional_pass:
                        prov = self.bus.meta_evaluate_provisional_fallback(self.stage, 
                            snap,
                            allow_provisional=self.allow_provisional,
                            strong_recovery_attempts=self.strong_recovery_attempts,
                            stage_trades=self.stage_trades,
                            required=self.required,
                            attempt=self.attempt,
                            patterns_mined=self.patterns_mined,
                            buffer_size=len(self.host.buffer),
                            constitution_violations=self.host._constitution_guard.violations,
                        )
                        self.provisional_pass_considered = True
                        self._log_provisional_pass_outcome(
                            source="self_eval_probe_complete",
                            should_grant=prov.should_grant,
                            blocked_reason=prov.blocked_reason,
                            safeguards=prov.safeguards,
                        )
                        if prov.should_grant:
                            self.gen0_provisional = True
                elif self.bus.meta_self_eval_state(self.stage).get('phase') == SelfEvalPhase.COMMITTED.value:
                    committed_plan = self.bus.meta_decide_committed_rollout(self.stage, snap)
                    self._apply_meta_plan(committed_plan, trigger="self_eval_committed")
                self.meta_message_suffix = self.bus.meta_format_self_eval_suffix(self.stage)
            else:
                next_attempt = self.attempt + 1
                should_review = (
                    (
                        next_attempt > 0
                        and next_attempt % self.cur_cfg.meta_review_interval_rollouts == 0
                    )
                    or stall_result.is_stalled
                    or rollout.stalled
                    or snap.learning_health == LearningHealth.DECLINING
                )
                exhausted_self_eval = (
                    self.cur_cfg.meta_self_eval_enabled
                    and self.bus.meta_self_eval_state(self.stage).get('phase') == SelfEvalPhase.EXHAUSTED.value
                )
                if exhausted_self_eval:
                    should_review = True
                review_plan: MetaActionPlan | None = None
                review_trigger = "periodic"
                if should_review:
                    if exhausted_self_eval:
                        review_plan = MetaActionPlan(
                            primary=RecoveryStrategy.HOLD,
                            suggest_provisional_pass=True,
                            rationale="self_eval_exhausted",
                            snapshot=snap,
                            self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
                        )
                        review_trigger = "self_eval_exhausted"
                    else:
                        review_trigger = (
                            "stall"
                            if stall_result.is_stalled or rollout.stalled
                            else "periodic"
                        )
                        review_plan = self.bus.meta_decide(self.stage, snap, trigger=review_trigger)
                    self._apply_meta_plan(review_plan, trigger=review_trigger)
                    if review_plan.suggest_provisional_pass:
                        prov = self.bus.meta_evaluate_provisional_fallback(self.stage, 
                            snap,
                            allow_provisional=self.allow_provisional,
                            strong_recovery_attempts=self.strong_recovery_attempts,
                            stage_trades=self.stage_trades,
                            required=self.required,
                            attempt=self.attempt,
                            patterns_mined=self.patterns_mined,
                            buffer_size=len(self.host.buffer),
                            constitution_violations=self.host._constitution_guard.violations,
                        )
                        self.provisional_pass_considered = True
                        self._log_provisional_pass_outcome(
                            source=(
                                "self_eval_exhausted"
                                if review_trigger == "self_eval_exhausted"
                                else "meta_review"
                            ),
                            should_grant=prov.should_grant,
                            blocked_reason=prov.blocked_reason,
                            safeguards=prov.safeguards,
                        )
                        if prov.should_grant:
                            self.gen0_provisional = True
                    if review_plan.enter_strong_recovery:
                        self._log_stall_event(
                            event="stall_detected",
                            stall=stall_result,
                            strong_recovery=True,
                        )
                        if (
                            self.cur_cfg.adaptation_enabled
                            and self.cur_cfg.wall_behavior == "adaptive"
                        ):
                            self._try_adaptive_stall_recovery(failure_key="velocity_stall")
                    elif review_plan.exit_strong_recovery:
                        self._log_stall_event(
                            event="stall_recovered",
                            stall=stall_result,
                            strong_recovery=False,
                        )
            if self.strong_recovery_mode:
                self.strong_recovery_attempts += 1
                prov = self.host._maybe_trigger_provisional_pass(
                    stage=self.stage,
                    stage_trades=self.stage_trades,
                    required=self.required,
                    attempt=self.attempt,
                    strong_recovery_attempts=self.strong_recovery_attempts,
                    patterns_mined=self.patterns_mined,
                    buffer_size=len(self.host.buffer),
                    constitution_violations=self.host._constitution_guard.violations,
                    combined_velocity=snap.combined_velocity,
                    allow_provisional=self.allow_provisional,
                    cfg=self.cur_cfg,
                )
                self.provisional_pass_considered = True
                self._log_provisional_pass_outcome(
                    source="strong_recovery",
                    should_grant=prov.should_grant,
                    blocked_reason=prov.blocked_reason,
                    safeguards=prov.safeguards,
                )
                if prov.should_grant:
                    self.gen0_provisional = True
        elif self.stage_trades >= self.required and rollout.trades > 0:
            stall_result = self.host._detect_stall(
                winrate_history=self.winrate_history,
                reward_history=self.reward_history,
                low_velocity_attempts=self.low_velocity_attempts,
                cfg=self.cur_cfg,
            )
            self.low_velocity_attempts = stall_result.low_velocity_attempts
            if stall_result.is_stalled:
                if not self.strong_recovery_mode:
                    self.strong_recovery_mode = True
                    self.strong_recovery_attempts = 0
                    self.escalation_level = min(
                        self.cur_cfg.max_escalation_level,
                        self.escalation_level + self.cur_cfg.strong_recovery_escalation_boost,
                    )
                    self.cur_cfg.rollout_chunk_trades = max(
                        self.cur_cfg.exploration_chunk_size,
                        self.cur_cfg.exploration_chunk_size * 2,
                    )
                    self.low_velocity_attempts = 0
                    self._log_stall_event(
                        event="stall_detected",
                        stall=stall_result,
                        strong_recovery=True,
                    )
                    self._mine_and_inject(aggressive=True)
                    if self.cur_cfg.adaptation_enabled and self.cur_cfg.wall_behavior == "adaptive":
                        self._try_adaptive_stall_recovery(failure_key="velocity_stall")
            elif (
                self.strong_recovery_mode
                and stall_result.combined_velocity > self.cur_cfg.velocity_stall_epsilon
            ):
                self.strong_recovery_mode = False
                self.strong_recovery_attempts = 0
                self.cur_cfg.rollout_chunk_trades = max(
                    self.cur_cfg.exploration_chunk_size,
                    self.original_rollout_chunk,
                )
                self._log_stall_event(
                    event="stall_recovered",
                    stall=stall_result,
                    strong_recovery=False,
                )
            if self.strong_recovery_mode:
                self.strong_recovery_attempts += 1
                prov = self.host._maybe_trigger_provisional_pass(
                    stage=self.stage,
                    stage_trades=self.stage_trades,
                    required=self.required,
                    attempt=self.attempt,
                    strong_recovery_attempts=self.strong_recovery_attempts,
                    patterns_mined=self.patterns_mined,
                    buffer_size=len(self.host.buffer),
                    constitution_violations=self.host._constitution_guard.violations,
                    combined_velocity=stall_result.combined_velocity,
                    allow_provisional=self.allow_provisional,
                    cfg=self.cur_cfg,
                )
                self.provisional_pass_considered = True
                self._log_provisional_pass_outcome(
                    source="strong_recovery_legacy",
                    should_grant=prov.should_grant,
                    blocked_reason=prov.blocked_reason,
                    safeguards=prov.safeguards,
                )
                if prov.should_grant:
                    self.gen0_provisional = True

