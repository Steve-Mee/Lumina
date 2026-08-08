"""Pre-rollout planning for a single curriculum cycle."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller import (
    MetaActionPlan,
    RecoveryStrategy,
)
from lumina_core.birth.meta_self_eval import SelfEvalPhase
from lumina_core.birth.plateau_escalator import (
    detect_hold_trap,
    detect_over_trading_trap,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.birth.stage_loop_rollout_pre_caps import StageLoopRolloutPreCapsMixin
from lumina_core.birth.stage_loop_rollout_types import RolloutPreState
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_rollout_pre")

__all__ = ["RolloutPreState", "StageLoopRolloutPreMixin"]



class StageLoopRolloutPreMixin(StageLoopRolloutPreCapsMixin, StageLoopMixinBase):
    """Build explore plan, traps, caps, and optional policy rollback before sim."""

    def _prepare_rollout_cycle(
        self, *, active_ticks: list[dict[str, Any]], chunk_target: int
    ) -> RolloutPreState:
        _ = active_ticks, chunk_target
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
            elif self.stage == CurriculumStage.STAGE3_MIXED:
                # Raptor v10: hold recovery also beyond pass-gate (was dead zone trades>=required).
                # Raptor v12: when hold is OK but WR still under floor → skill explore.
                hold_cap = float(
                    getattr(self.cur_cfg, "stage3_hold_ratio_max", 0.70) or 0.70
                )
                wr_floor = float(
                    getattr(self.cur_cfg, "stage3_winrate_floor", 0.35) or 0.35
                )
                velocity_hot = self.low_velocity_attempts >= max(
                    8, int(self.cur_cfg.velocity_stall_attempt_threshold) // 2
                )
                beyond_or_at_gate = self.stage_trades >= self.required
                if current_hold > hold_cap and (
                    beyond_or_at_gate or velocity_hot or current_hold > 0.75
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
                        "hold_cap=%.0f%% velocity_stall_attempts=%s",
                        self.stage_trades,
                        self.required,
                        current_hold * 100.0,
                        hold_cap * 100.0,
                        self.low_velocity_attempts,
                    )
                elif (
                    current_hold <= hold_cap
                    and current_wr < wr_floor
                    and beyond_or_at_gate
                ):
                    # Raptor v14: low-hold + low-WR → selectivity, not more random explore.
                    if current_hold < 0.40:
                        pre_plan = MetaActionPlan(
                            primary=RecoveryStrategy.EXPLORE_REDUCE,
                            explore_steps=max(
                                200,
                                int(
                                    self.cur_cfg.exploration_steps
                                    * float(
                                        getattr(
                                            self.cur_cfg,
                                            "strong_recovery_explore_fraction",
                                            0.35,
                                        )
                                        or 0.35
                                    )
                                ),
                            ),
                            escalation_delta=1,
                            mine=True,
                            mine_aggressive=True,
                            rationale="stage3_wr_recovery_selectivity",
                            snapshot=pre_snap,
                        )
                        logger.info(
                            "birth.stage3_wr_recovery_selectivity stage_trades=%s/%s "
                            "wr=%.1f%% floor=%.0f%% hold=%.1f%%",
                            self.stage_trades,
                            self.required,
                            current_wr * 100.0,
                            wr_floor * 100.0,
                            current_hold * 100.0,
                        )
                    else:
                        pre_plan = MetaActionPlan(
                            primary=RecoveryStrategy.EXPLORE_BOOST,
                            explore_steps=max(
                                base_explore_steps,
                                int(self.cur_cfg.exploration_steps) * 3,
                            ),
                            escalation_delta=1,
                            mine=True,
                            mine_aggressive=True,
                            rationale="stage3_wr_recovery_explore",
                            snapshot=pre_snap,
                        )
                        logger.info(
                            "birth.stage3_wr_recovery stage_trades=%s/%s wr=%.1f%% "
                            "floor=%.0f%% hold=%.1f%%",
                            self.stage_trades,
                            self.required,
                            current_wr * 100.0,
                            wr_floor * 100.0,
                            current_hold * 100.0,
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
        return self._finish_rollout_pre_caps(
            explore_steps=explore_steps,
            reward_override=reward_override,
            progress_cb=_rollout_progress,
        )
