"""Single-rollout cycle: pre-meta, sim rollout, post-update."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    is_runway_stage,
    update_stage1_intra_state,
    update_stage2_intra_state,
)
from lumina_core.birth.meta_controller import (
    LearningHealth,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
)
from lumina_core.birth.meta_self_eval import SelfEvalPhase
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    detect_hold_trap,
    detect_over_trading_trap,
    is_valid_best_policy_snapshot,
    update_plateau_quarantine_after_rollout,
)
from lumina_core.birth.sim_runner import run_policy_rollout
from lumina_core.birth.stall_remediation import HUMAN_GATE_REASON
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_rollout_cycle")


class StageLoopRolloutCycleMixin(StageLoopMixinBase):
    """Execute one curriculum rollout cycle (meta + sim + metrics update)."""

    def _execute_rollout_cycle(self, *, active_ticks: list[dict[str, Any]], chunk_target: int) -> dict[str, Any] | None:
        """Returns a terminal stall dict to return from run(), or None to continue the loop."""
        self.chunk_trades_snapshot = 0

        def _rollout_progress(snapshot: dict[str, Any]) -> None:
            self.chunk_trades_snapshot = int(snapshot.get("rollout_trades", 0) or 0)
            explore_suffix = " (exploratie actief)" if snapshot.get("exploration_active") else ""
            self._write_progress(
                phase="curriculum_learning",
                message=(
                    f"Curriculum {self.stage.value}: {self.stage_trades + self.chunk_trades_snapshot:,} / "
                    f"{self.required:,} trades · poging {self.attempt + 1} · L{self.escalation_level} · "
                    f"patronen {self.patterns_mined:,}{explore_suffix}"
                ),
                chunk_trades=self.chunk_trades_snapshot,
                rollout_steps=int(snapshot.get("rollout_steps", 0) or 0),
                exploration_active=bool(snapshot.get("exploration_active")),
                hold_ratio=float(snapshot.get("hold_ratio", 0.0) or 0.0),
            )

        base_explore_steps = self.cur_cfg.exploration_steps * (1 + self.escalation_level)
        reward_override = None
        if self.cur_cfg.meta_controller_enabled:
            pre_snap, _ = self._observe_snapshot()
            if self.cur_cfg.meta_self_eval_enabled:
                self.bus.meta_maybe_start_self_eval(self.stage, 
                    pre_snap,
                    strong_recovery_attempts=self.strong_recovery_attempts,
                    attempt=self.attempt + 1,
                )
            if (
                self.cur_cfg.meta_self_eval_enabled
                and bool(self.bus.meta_self_eval_state(self.stage).get('active', False))
            ):
                if self.bus.meta_self_eval_state(self.stage).get('phase') == SelfEvalPhase.PROBING.value:
                    pre_plan = self.bus.meta_decide_probe_rollout(self.stage, pre_snap)
                elif self.bus.meta_self_eval_state(self.stage).get('phase') == SelfEvalPhase.COMMITTED.value:
                    pre_plan = self.bus.meta_decide_committed_rollout(self.stage, pre_snap)
                else:
                    pre_plan = MetaActionPlan(
                        primary=RecoveryStrategy.HOLD,
                        rationale="self_eval_exhausted",
                        snapshot=pre_snap,
                        self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
                    )
            else:
                pre_plan = self.bus.meta_decide_pre_rollout(
                    self.stage,
                    pre_snap,
                    base_explore_steps=base_explore_steps,
                    wall_budget_exhausted=self.wall_budget_exhausted,
                    winrate_stagnation_count=self.winrate_stagnation_count,
                    hold_stagnation_count=self.hold_stagnation_count,
                )
            current_wr = float(self.stage_wins) / float(max(1, self.stage_trades))
            current_hold = (
                float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
                if self.stage_total_signals
                else 0.0
            )
            if detect_hold_trap(
                hold_ratio=current_hold,
                winrate=current_wr,
                pass_metric_target=self.pass_metric_target,
                velocity_stall=self.low_velocity_attempts
                >= int(self.cur_cfg.velocity_stall_attempt_threshold),
                cfg=self.cur_cfg,
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_BOOST,
                    explore_steps=max(
                        base_explore_steps,
                        int(self.cur_cfg.exploration_steps) * 4,
                    ),
                    escalation_delta=1,
                    rationale="hold_trap_forced_explore",
                    snapshot=pre_snap,
                )
                if not self.hold_trap_milestone_sent:
                    self.hold_trap_milestone_sent = True
                    try:
                        from lumina_core.notifications.milestone_events import (
                            hold_trap_detected_event,
                        )

                        self.host._notify_milestone(
                            hold_trap_detected_event(
                                hold_ratio=current_hold,
                                winrate=current_wr,
                            )
                        )
                    except Exception as exc:
                        logger.debug("birth.milestone_hold_trap_failed: %s", exc)
            elif (
                self.stage == CurriculumStage.STAGE3_MIXED
                and self.stage_trades < self.required
                and current_hold > 0.75
                and self.low_velocity_attempts
                >= max(8, int(self.cur_cfg.velocity_stall_attempt_threshold) // 2)
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_BOOST,
                    explore_steps=max(
                        base_explore_steps,
                        int(self.cur_cfg.exploration_steps) * 4,
                    ),
                    escalation_delta=1,
                    rationale="stage3_hold_recovery_explore",
                    snapshot=pre_snap,
                )
                logger.info(
                    "birth.stage3_hold_recovery stage_trades=%s/%s hold_ratio=%.1f%% "
                    "velocity_stall_attempts=%s",
                    self.stage_trades,
                    self.required,
                    current_hold * 100.0,
                    self.low_velocity_attempts,
                )
            elif (
                self.stage == CurriculumStage.STAGE2_RANGE
                and detect_over_trading_trap(
                    range_flat_ratio=float(self.stage_range_flat_bars)
                    / float(max(1, self.stage_range_total_signals)),
                    range_round_trips=self.stage_range_round_trips,
                    required=self.required,
                    velocity_stall=self.low_velocity_attempts
                    >= int(self.cur_cfg.velocity_stall_attempt_threshold),
                    cfg=self.cur_cfg,
                )
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_REDUCE,
                    explore_steps=max(
                        200,
                        int(self.cur_cfg.exploration_steps * self.cur_cfg.strong_recovery_explore_fraction),
                    ),
                    escalation_delta=1,
                    rationale="over_trading_range_patience",
                    snapshot=pre_snap,
                )
                if not self.over_trading_milestone_sent:
                    self.over_trading_milestone_sent = True
                    logger.info(
                        "birth.over_trading_trap_detected stage=%s flat_ratio=%.2f%% round_trips=%s",
                        self.stage.value,
                        100.0
                        * float(self.stage_range_flat_bars)
                        / float(max(1, self.stage_range_total_signals)),
                        self.stage_range_round_trips,
                    )
            elif (
                pre_plan.primary == RecoveryStrategy.HOLD
                and self._meta_self_eval_phase_str() == "exhausted"
                and self.plateau_state.active
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_BOOST,
                    explore_steps=max(
                        base_explore_steps,
                        int(self.cur_cfg.exploration_steps) * 4,
                    ),
                    escalation_delta=1,
                    rationale="meta_exhausted_forced_explore",
                    snapshot=pre_snap,
                )
            if pre_plan.mine:
                self._mine_and_inject(aggressive=pre_plan.mine_aggressive)
            if pre_plan.escalation_delta > 0:
                self.escalation_level = min(
                    self.cur_cfg.max_escalation_level,
                    self.escalation_level + pre_plan.escalation_delta,
                )
            elif pre_plan.escalation_delta < 0:
                self.escalation_level = max(0, self.escalation_level + pre_plan.escalation_delta)
            explore_steps = self.bus.meta_apply_explore_multiplier(self.stage, 
                pre_plan.explore_steps or base_explore_steps,
            )
            self.meta_last_plan = pre_plan
            if pre_plan.primary != RecoveryStrategy.HOLD or pre_plan.mine or pre_plan.expand_data:
                self._log_meta_decision(pre_plan, trigger="pre_rollout")
            if bool(self.bus.meta_self_eval_state(self.stage).get('reward_tweak_active', False)):
                reward_override = self.bus.meta_controller.active_reward
        else:
            explore_steps = base_explore_steps
            if not self.strong_recovery_mode:
                if (
                    self.stage == CurriculumStage.STAGE2_RANGE
                    and self.stage_trades >= self.required
                    and self.hold_stagnation_count >= self.cur_cfg.stage2_hold_stagnation_rollouts
                ):
                    explore_steps = max(explore_steps, self.cur_cfg.exploration_steps * 4)
                    self.escalation_level = min(self.cur_cfg.max_escalation_level, self.escalation_level + 1)
                if (
                    self.stage == CurriculumStage.STAGE1_TREND
                    and self.stage_trades >= self.required
                    and self.winrate_stagnation_count >= self.cur_cfg.stage1_winrate_stagnation_rollouts
                ):
                    explore_steps = max(explore_steps, self.cur_cfg.exploration_steps * 4)
                    self.escalation_level = min(self.cur_cfg.max_escalation_level, self.escalation_level + 1)
                    self._mine_and_inject()
                if self.wall_budget_exhausted:
                    explore_steps = max(explore_steps, self.cur_cfg.exploration_steps * 4)
            else:
                if (
                    self.strong_recovery_attempts > 0
                    and self.strong_recovery_attempts
                    % self.cur_cfg.strong_recovery_expand_every_attempts
                    == 0
                ):
                    self._maybe_expand_data()
                    self._mine_and_inject(aggressive=True)
                explore_steps = max(
                    200,
                    int(
                        self.cur_cfg.exploration_steps
                        * self.cur_cfg.strong_recovery_explore_fraction
                    ),
                )
        pre_rollout_hold = (
            float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
            if self.stage_total_signals
            else 0.0
        )
        pre_rollout_flat = (
            float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals))
            if self.stage_range_total_signals
            else 0.0
        )
        if self.swarm_state.active:
            swarm_reward, swarm_explore_mult = self._apply_swarm_variant_for_rollout()
            if swarm_reward is not None:
                reward_override = swarm_reward
            explore_steps = max(200, int(explore_steps * swarm_explore_mult))
        plateau_recovery = self.plateau_state.active or self.remediation_state.active
        hold_cap: float | None = None
        position_flat_cap: float | None = None
        range_patience_active = self.stage == CurriculumStage.STAGE2_RANGE
        velocity_stalled = self.low_velocity_attempts >= int(self.cur_cfg.velocity_stall_attempt_threshold)
        if plateau_recovery or detect_hold_trap(
            hold_ratio=pre_rollout_hold,
            winrate=float(self.stage_wins) / float(max(1, self.stage_trades)),
            pass_metric_target=self.pass_metric_target,
            velocity_stall=velocity_stalled,
            cfg=self.cur_cfg,
        ):
            hold_cap = float(self.cur_cfg.hold_trap_recovery_hold_cap)
        if self.stage == CurriculumStage.STAGE2_RANGE and detect_over_trading_trap(
            range_flat_ratio=pre_rollout_flat,
            range_round_trips=self.stage_range_round_trips,
            required=self.required,
            velocity_stall=velocity_stalled,
            cfg=self.cur_cfg,
        ):
            position_flat_cap = float(self.cur_cfg.over_trading_recovery_flat_target)
            range_patience_active = True
        if (
            self.plateau_state.best_policy_path
            and is_valid_best_policy_snapshot(self.plateau_state, cfg=self.cur_cfg)
            and self.attempt - self.last_policy_rollback_attempt
            >= int(self.cur_cfg.policy_rollback_cooldown_rollouts)
        ):
            live_wr = float(self.stage_wins) / float(max(1, self.stage_trades))
            rollback_wr_gap = live_wr + float(self.cur_cfg.policy_rollback_winrate_gap) < (
                self.plateau_state.best_winrate
            )
            should_rollback = rollback_wr_gap and (
                self.strong_recovery_mode
                or (
                    self.stage == CurriculumStage.STAGE3_MIXED
                    and self.stage_trades < self.required
                    and pre_rollout_hold > 0.75
                )
            )
            if should_rollback:
                detail, applied = self._apply_plateau_evolution_action(
                    EvolutionAction.POLICY_ROLLBACK
                )
                if applied:
                    self.last_policy_rollback_attempt = self.attempt
                logger.info(
                    "birth.policy_rollback_auto_applied detail=%s applied=%s live_wr=%.2f%% best=%.2f%% "
                    "stage=%s hold_ratio=%.1f%%",
                    detail,
                    applied,
                    live_wr * 100.0,
                    self.plateau_state.best_winrate * 100.0,
                    self.stage.value,
                    pre_rollout_hold * 100.0,
                )
        rollout_started_at = time.time()
        rollout = run_policy_rollout(
            runtime=self.host.runtime,
            data=active_ticks,
            policy=self.host.current_policy,
            target_trades=chunk_target,
            workspace_root=self.host.workspace_root,
            constitution_guard=self.host._constitution_guard,
            rollout_step_budget=self.chunk_budget,
            stall_probe_steps=max(200, self.cur_cfg.stall_probe_steps // (1 + self.escalation_level)),
            exploration_steps=explore_steps,
            escalation_level=self.escalation_level,
            hold_cap_ratio=hold_cap,
            position_flat_cap=position_flat_cap,
            range_patience_active=range_patience_active,
            plateau_active=plateau_recovery,
            on_progress=_rollout_progress,
            reward_override=reward_override,
        )
        self.rollout_wall_clock_total_sec += max(0.0, time.time() - rollout_started_at)
        self.rollout_wall_clock_samples += 1
        self.sim_ticks_processed_cumulative += int(getattr(rollout, "rollout_steps", 0) or 0)

        self.stage_trades += rollout.trades
        self.stage_wins += rollout.wins
        self.stage_hold_signals += rollout.hold_signals
        self.stage_total_signals += rollout.total_signals
        self.stage_range_hold_signals += rollout.range_hold_signals
        self.stage_range_total_signals += rollout.range_total_signals
        self.stage_range_flat_bars += rollout.range_flat_bars
        self.stage_range_round_trips += rollout.range_round_trips
        self.host.cumulative_trades += rollout.trades
        self._maybe_run_oos_proxy()
        self._maybe_record_and_advance_swarm(
            trades=rollout.trades,
            wins=rollout.wins,
            total_pnl=float(rollout.total_pnl),
        )
        if is_runway_stage(self.stage):
            self.stage_val_pnl.extend(rollout.pnl_series)

        if self.intra_state is not None and rollout.easy_trades > 0:
            update_stage1_intra_state(
                self.intra_state,
                chunk_easy_trades=rollout.easy_trades,
                chunk_easy_wins=rollout.easy_wins,
                cfg=self.cur_cfg,
            )
        if self.intra_s2_state is not None and rollout.range_total_signals > 0:
            easy_share = 0.0
            if self.current_intra_sample_pool:
                easy_count = sum(
                    1
                    for t in self.current_intra_sample_pool
                    if str(t.get("_intra_difficulty", "")).lower() == "easy"
                )
                easy_share = float(easy_count) / float(max(1, len(self.current_intra_sample_pool)))
            if easy_share > 0.0:
                update_stage2_intra_state(
                    self.intra_s2_state,
                    chunk_flat_bars=int(rollout.range_flat_bars * easy_share),
                    chunk_range_signals=max(
                        1, int(rollout.range_total_signals * easy_share)
                    ),
                    cfg=self.cur_cfg,
                )

        current_hold_ratio = float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
        range_flat_ratio = float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals))
        if self.stage == CurriculumStage.STAGE2_RANGE and rollout.range_total_signals > 0:
            rollout_flat = float(rollout.range_flat_bars) / float(max(1, rollout.range_total_signals))
            flat_delta = range_flat_ratio - self.last_range_flat_ratio
            logger.info(
                "birth.stage2.rollout_metrics rollout_flat=%.4f stage_flat=%.4f delta=%+.4f "
                "round_trips=%s trades=%s",
                rollout_flat,
                range_flat_ratio,
                flat_delta,
                rollout.range_round_trips,
                rollout.trades,
            )
            self.last_range_flat_ratio = range_flat_ratio
        if rollout.trades > 0:
            self.wins_at_trade_milestones[self.stage_trades] = self.stage_wins
        metric_band = range_flat_ratio if self.stage_range_total_signals >= 50 else current_hold_ratio
        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        if rollout.trades > 0:
            self.winrate_history.append(current_winrate)
            if len(self.winrate_history) > self.cur_cfg.winrate_trend_window:
                self.winrate_history.pop(0)
            mean_reward = float(rollout.total_pnl) / float(max(1, rollout.trades))
            self.reward_history.append(mean_reward)
            if len(self.reward_history) > self.cur_cfg.reward_trend_window:
                self.reward_history.pop(0)

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

        if (
            self.stage == CurriculumStage.STAGE1_TREND
            and self.stage_trades >= self.required
            and (current_winrate < self.pass_metric_target or current_hold_ratio > 0.85)
        ):
            if abs(current_winrate - self.last_winrate) < 0.01 and abs(
                current_hold_ratio - self.last_hold_ratio
            ) < 0.01:
                self.winrate_stagnation_count += 1
            else:
                self.winrate_stagnation_count = 0
            self.last_winrate = current_winrate
            self.last_hold_ratio = current_hold_ratio
        elif (
            self.stage == CurriculumStage.STAGE2_RANGE
            and self.stage_trades >= self.required
            and (metric_band > 0.70 or metric_band < 0.30)
        ):
            if abs(metric_band - self.last_hold_ratio) < 0.01:
                self.hold_stagnation_count += 1
            else:
                self.hold_stagnation_count = 0
            self.last_hold_ratio = metric_band
        else:
            self.hold_stagnation_count = 0
            if self.stage != CurriculumStage.STAGE1_TREND:
                self.winrate_stagnation_count = 0

        for traj in rollout.trajectories:
            self.host.buffer.add(traj, priority=1.0 + min(10.0, abs(float(traj.get("reward", 0.0)))))

        if len(self.host.buffer) >= 256:
            stage_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
            self._write_progress(
                phase="ppo_training",
                message=(
                    f"PPO batch start · {self.stage_trades:,}/{self.required:,} trades · "
                    f"winrate {stage_winrate:.1%} · patronen {self.patterns_mined:,}"
                ),
                hold_ratio=float(self.stage_hold_signals) / float(max(1, self.stage_total_signals)),
            )
            self.host.current_policy = self.host.ppo_trainer.update_from_buffer(
                buffer=self.host.buffer,
                timesteps=self.ppo_steps_per_update,
                birth_phase=True,
            )
            self.host.ppo_steps += self.ppo_steps_per_update
            self.host._persist_checkpoint(
                training_mode=self.training_mode,
                curriculum_stage=self.stage.value,
                phase="ppo_training",
                stage_metrics=self._stage_metrics_payload(),
            )

        if rollout.stalled and self.stage_trades == 0 and self.patterns_mined == 0:
            self.escalation_level += 1
            if self.escalation_level >= self.cur_cfg.max_escalation_level:
                self._mine_and_inject()
                self._maybe_expand_data()
                self.escalation_level = 0
        elif rollout.trades == 0 or rollout.partial_complete:
            self.escalation_level = min(self.escalation_level + 1, self.cur_cfg.max_escalation_level - 1)
        elif rollout.trades < max(1, chunk_target // 4):
            self.escalation_level = min(self.escalation_level + 1, self.cur_cfg.max_escalation_level - 1)

        self.attempt += 1
        for pct in (50, 75, 90):
            if (
                pct not in self.budget_milestones_notified
                and self.effective_trade_budget_cap > 0
                and self.host.cumulative_trades * 100 // self.effective_trade_budget_cap >= pct
            ):
                self.budget_milestones_notified.add(pct)
                try:
                    from lumina_core.notifications.milestone_events import (
                        trade_budget_milestone_event,
                    )

                    self.host._notify_milestone(
                        trade_budget_milestone_event(
                            pct=pct,
                            cumulative_trades=self.host.cumulative_trades,
                            cap=self.effective_trade_budget_cap,
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_budget_failed: %s", exc)
        if self.winrate_history:
            prior_mean = sum(self.winrate_history) / float(len(self.winrate_history))
            if current_winrate >= prior_mean + 0.02:
                try:
                    from lumina_core.notifications.milestone_events import (
                        learning_breakthrough_event,
                    )

                    self.host._notify_milestone(
                        learning_breakthrough_event(
                            winrate=current_winrate,
                            prior_mean=prior_mean,
                            delta=current_winrate - prior_mean,
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_breakthrough_failed: %s", exc)
        if self.plateau_state.active:
            self.bus.plateau_increment_rollout(self.stage)
            failure_key_rollout = {
                CurriculumStage.STAGE1_TREND: "stage1_winrate",
                CurriculumStage.STAGE2_RANGE: "stage2_metric",
                CurriculumStage.STAGE3_MIXED: "stage3_constitution",
            }.get(self.stage, "stage_metrics")
            if self._try_evolution_exhausted_remediation(failure_key=failure_key_rollout):
                self.attempt = 0
            else:
                self._maybe_advance_plateau_evolution_in_loop()
        if self.remediation_state.active:
            self.bus.remediation_increment_rollout(self.stage)
            if self._maybe_advance_stall_remediation_in_loop():
                pending = self._plateau_terminal_pending(failure_key="stage1_winrate") or {
                    "failure_key": "stage1_winrate",
                    "blocker_metric": "trend_winrate",
                    "blocker_value": float(self.stage_wins) / float(max(1, self.stage_trades)),
                    "blocker_reason": HUMAN_GATE_REASON,
                    "terminal_stall_reason": HUMAN_GATE_REASON,
                }
                human_gate = not self.cur_cfg.autonomous_recovery_enabled
                stall_result = self._finalize_certified_stage_stall(
                    pending,
                    human_gate=human_gate,
                )
                return stall_result
        update_plateau_quarantine_after_rollout(
            self.plateau_quarantine,
            stage_trades=self.stage_trades,
        )
        self._maybe_detect_plateau(stage_trades=self.stage_trades, stage_wins=self.stage_wins)
        self._maybe_save_best_policy(stage_trades=self.stage_trades, stage_wins=self.stage_wins)
        self._maybe_periodic_checkpoint("curriculum_learning")
        self._write_progress(
            phase="curriculum_learning",
            message=(
                f"Curriculum {self.stage.value}: {self.stage_trades:,} / {self.required:,} trades · "
                f"poging {self.attempt} · patronen {self.patterns_mined:,}{self.meta_message_suffix}"
            ),
            hold_ratio=current_hold_ratio,
        )
        self.meta_message_suffix = ""
        return None
