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
        _ = chunk_target
        # Birth trade geometry SSOT — NEVER recalibrate on shuffled active_ticks.
        # Reuse stage-entry frozen geometry; optional re-cal only on chronological
        # active_stage_ticks / active_train (same plant law as stage_prepare).
        try:
            from lumina_core.birth.birth_trade_geometry import (
                BirthTradeGeometry,
                calibrate_birth_stops,
            )

            frozen = getattr(self, "_birth_trade_geometry", None)
            if frozen is not None and float(getattr(frozen, "stop_pct", 0.0) or 0.0) > 0:
                geo = frozen
            else:
                chrono = list(
                    getattr(self, "active_stage_ticks", None)
                    or getattr(self, "active_train", None)
                    or []
                )
                # Fail closed: if only active_ticks available, still call calibrate
                # (now rejects disordered peak-move) rather than inherit 0.008.
                if len(chrono) < 40:
                    chrono = list(active_ticks or [])
                hold = max(
                    20, int(getattr(self.cur_cfg, "oracle_max_hold_bars", 90) or 90)
                )
                geo = calibrate_birth_stops(chrono, max_hold_bars=hold)
                self._birth_trade_geometry = geo
            self._birth_trade_stop_pct = float(geo.stop_pct)
            self._birth_trade_target_pct = float(geo.target_pct)
            self._birth_trade_geometry_source = str(geo.source)
            self._birth_geometry_hold_bars = int(
                getattr(geo, "hold_bars", 0) or hold or 120
            )
        except Exception:
            self._birth_trade_stop_pct = float(
                getattr(self, "_birth_trade_stop_pct", 0.0012) or 0.0012
            )
            self._birth_trade_target_pct = float(
                getattr(self, "_birth_trade_target_pct", 0.0020) or 0.0020
            )
            if getattr(self, "_birth_trade_geometry", None) is None:
                from lumina_core.birth.birth_trade_geometry import BirthTradeGeometry

                self._birth_trade_geometry = BirthTradeGeometry(
                    stop_pct=float(self._birth_trade_stop_pct),
                    target_pct=float(self._birth_trade_target_pct),
                    source="fallback_rollout_pre",
                )
            if not int(getattr(self, "_birth_geometry_hold_bars", 0) or 0):
                self._birth_geometry_hold_bars = 120
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
            current_flat = (
                float(self.stage_range_flat_bars)
                / float(max(1, self.stage_range_total_signals))
                if int(getattr(self, "stage_range_total_signals", 0) or 0)
                else 0.0
            )
            quality_lock = False
            try:
                peak_st = getattr(self, "stage2_peak_state", None)
                quality_lock = bool(getattr(peak_st, "quality_lock_active", False))
            except Exception:
                quality_lock = False
            quality_explore = max(
                200,
                int(
                    self.cur_cfg.exploration_steps
                    * float(
                        getattr(self.cur_cfg, "strong_recovery_explore_fraction", 0.35)
                        or 0.35
                    )
                ),
            )
            if quality_lock:
                pass  # Peak quality lock: never hold_trap explore_boost over the 42% policy.
            elif detect_hold_trap(
                hold_ratio=current_hold,
                winrate=current_wr,
                pass_metric_target=self.pass_metric_target,
                velocity_stall=self.low_velocity_attempts
                >= int(self.cur_cfg.velocity_stall_attempt_threshold),
                cfg=self.cur_cfg,
                range_flat_ratio=current_flat,
            ):
                pre_plan = MetaActionPlan(
                    primary=RecoveryStrategy.EXPLORE_REDUCE,
                    explore_steps=quality_explore,
                    escalation_delta=1,
                    rationale="hold_trap_quality_reduce",
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
                # Occupancy in band: high HOLD% is geometry, not a hold-trap.
                # Recover on WR/expectancy, never fight the envelope with anti-hold.
                occupancy_in_band = 0.25 <= current_flat <= 0.75
                wr_floor = float(
                    getattr(self.cur_cfg, "stage3_winrate_floor", 0.35) or 0.35
                )
                velocity_hot = self.low_velocity_attempts >= max(
                    8, int(self.cur_cfg.velocity_stall_attempt_threshold) // 2
                )
                beyond_or_at_gate = self.stage_trades >= self.required
                if occupancy_in_band and current_wr < wr_floor and beyond_or_at_gate:
                    pre_plan = MetaActionPlan(
                        primary=RecoveryStrategy.EXPLORE_REDUCE,
                        explore_steps=quality_explore,
                        escalation_delta=1,
                        mine=True,
                        mine_aggressive=True,
                        rationale="stage3_wr_recovery_selectivity",
                        snapshot=pre_snap,
                    )
                    logger.info(
                        "birth.stage3_wr_recovery_selectivity stage_trades=%s/%s "
                        "wr=%.1f%% floor=%.0f%% hold=%.1f%% flat=%.1f%%",
                        self.stage_trades,
                        self.required,
                        current_wr * 100.0,
                        wr_floor * 100.0,
                        current_hold * 100.0,
                        current_flat * 100.0,
                    )
                elif (not occupancy_in_band) and current_flat > 0.75 and (
                    beyond_or_at_gate or velocity_hot
                ):
                    pre_plan = MetaActionPlan(
                        primary=RecoveryStrategy.EXPLORE_REDUCE,
                        explore_steps=quality_explore,
                        escalation_delta=1,
                        rationale="stage3_under_activity_reduce",
                        snapshot=pre_snap,
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
                not quality_lock
                and pre_plan.primary == RecoveryStrategy.HOLD
                and self._meta_self_eval_phase_str() == "exhausted"
                and self.plateau_state.active
            ):
                s2s3 = self.stage in (
                    CurriculumStage.STAGE2_RANGE,
                    CurriculumStage.STAGE3_MIXED,
                )
                pre_plan = MetaActionPlan(
                    primary=(
                        RecoveryStrategy.EXPLORE_REDUCE
                        if s2s3
                        else RecoveryStrategy.EXPLORE_BOOST
                    ),
                    explore_steps=(
                        quality_explore
                        if s2s3
                        else max(
                            base_explore_steps,
                            int(self.cur_cfg.exploration_steps) * 4,
                        )
                    ),
                    escalation_delta=1,
                    rationale=(
                        "meta_exhausted_quality_reduce"
                        if s2s3
                        else "meta_exhausted_forced_explore"
                    ),
                    snapshot=pre_snap,
                )
            try:
                from lumina_core.birth.expectancy_stall import (
                    apply_pre_rollout_quality_coerce,
                )

                original_primary = str(
                    getattr(getattr(pre_plan, "primary", None), "value", pre_plan.primary)
                    or ""
                )
                pre_plan = apply_pre_rollout_quality_coerce(
                    pre_plan,
                    loop=self,
                    cfg=self.cur_cfg,
                    base_explore_steps=int(base_explore_steps),
                )
                new_primary = str(
                    getattr(getattr(pre_plan, "primary", None), "value", pre_plan.primary)
                    or ""
                )
                if (
                    original_primary.lower() == "explore_boost"
                    and new_primary.lower() != "explore_boost"
                ):
                    logger.info(
                        "birth.pre_rollout.quality_coerce from=%s to=%s rationale=%s "
                        "explore_steps=%s",
                        original_primary,
                        new_primary,
                        getattr(pre_plan, "rationale", ""),
                        int(getattr(pre_plan, "explore_steps", 0) or 0),
                    )
            except Exception as exc:
                logger.debug("birth.pre_rollout.quality_coerce_failed: %s", exc)
            if quality_lock and current_wr + 1e-12 < 0.30:
                # Peak lock + weak lifetime: distill peak winners, never explore_boost.
                try:
                    from dataclasses import replace

                    pre_plan = replace(pre_plan, mine=True, mine_aggressive=False)
                except Exception:
                    pass
            if pre_plan.mine:
                self._mine_and_inject(aggressive=pre_plan.mine_aggressive)
            if pre_plan.escalation_delta > 0:
                self.escalation_level = min(
                    self.cur_cfg.max_escalation_level,
                    self.escalation_level + pre_plan.escalation_delta,
                )
            elif pre_plan.escalation_delta < 0:
                self.escalation_level = max(0, self.escalation_level + pre_plan.escalation_delta)
            explore_steps = int(pre_plan.explore_steps or base_explore_steps)
            primary_s = str(
                getattr(getattr(pre_plan, "primary", None), "value", pre_plan.primary) or ""
            ).lower()
            if primary_s == "explore_boost":
                explore_steps = self.bus.meta_apply_explore_multiplier(
                    self.stage, explore_steps
                )
            else:
                explore_steps = max(200, int(explore_steps))
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
                    try:
                        from lumina_core.birth.expectancy_stall import loop_expectancy_stall

                        quality_owns = loop_expectancy_stall(self, cfg=self.cur_cfg)
                    except Exception:
                        quality_owns = False
                    if quality_owns:
                        explore_steps = max(
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
                        )
                    else:
                        explore_steps = max(explore_steps, self.cur_cfg.exploration_steps * 4)
                        self.escalation_level = min(
                            self.cur_cfg.max_escalation_level, self.escalation_level + 1
                        )
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
