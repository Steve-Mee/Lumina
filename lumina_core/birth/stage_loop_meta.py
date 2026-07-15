"""StageLoopMetaMixin — StageLoopSession mixin."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.birth_bus_serde import reward_config_to_dict
from lumina_core.birth.meta_controller import (
    BirthMetaController,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class StageLoopMetaMixin(StageLoopMixinBase):
    """See StageLoopSession for attributes."""

    def _observe_snapshot(self) -> tuple[Any, StallDetectionResult]:
        return self.bus.meta_observe(
            self.stage,
            winrate_history=self.winrate_history,
            reward_history=self.reward_history,
            stage_trades=self.stage_trades,
            required_trades=self.required,
            patterns_mined=self.patterns_mined,
            buffer_size=len(self.host.buffer),
            escalation_level=self.escalation_level,
            strong_recovery_mode=self.strong_recovery_mode,
            strong_recovery_attempts=self.strong_recovery_attempts,
            low_velocity_attempts=self.low_velocity_attempts,
            data_exhausted=self.data_exhausted,
            intra_hard_pct=self.intra_state.hard_pct if self.intra_state else None,
            attempt=self.attempt,
            range_flat_ratio=float(self.stage_range_flat_bars)
            / float(max(1, self.stage_range_total_signals)),
            range_round_trips=self.stage_range_round_trips,
            oos_proxy_history=self.oos_proxy_history,
            constitution_violations=self.host._constitution_guard.violations,
        )

    def _maybe_run_oos_proxy(self) -> None:
        from lumina_core.birth.oos_proxy import run_oos_proxy_eval, should_run_oos_proxy

        if not should_run_oos_proxy(
            self.host.cumulative_trades,
            self.last_oos_proxy_at_trades,
            cfg=self.cur_cfg,
        ):
            return
        if not self.holdout_ticks_ref:
            return
        try:
            result = run_oos_proxy_eval(
                runtime=self.host.runtime,
                holdout_ticks=self.holdout_ticks_ref,
                policy=self.host.current_policy,
                workspace_root=self.host.workspace_root,
                constitution_guard=self.host._constitution_guard,
                cfg=self.cur_cfg,
            )
        except Exception as exc:
            logger.debug("birth.oos_proxy_failed: %s", exc)
            return
        proxy_wr = float(result.get("oos_proxy_winrate", 0.0) or 0.0)
        self.oos_proxy_history.append(proxy_wr)
        if len(self.oos_proxy_history) > self.cur_cfg.winrate_trend_window:
            self.oos_proxy_history.pop(0)
        self.last_oos_proxy_at_trades = int(self.host.cumulative_trades)
        logger.info(
            "birth.oos_proxy winrate=%.2f%% trades=%s cumulative=%s",
            proxy_wr * 100.0,
            result.get("oos_proxy_trades", 0),
            self.host.cumulative_trades,
        )

    def _log_meta_decision(self, plan: MetaActionPlan, trigger: str) -> None:
        event = BirthMetaController.format_decision_log(plan, trigger=trigger)
        logger.info(
            "birth.meta.decision trigger=%s primary=%s rationale=%s "
            "health=%s combined_velocity=%.6f is_stalled=%s",
            event.get("trigger"),
            event.get("primary"),
            event.get("rationale"),
            event.get("learning_health"),
            float(event.get("combined_velocity", 0.0) or 0.0),
            event.get("is_stalled"),
            extra={"event_data": event},
        )

    def _log_stall_event(self, 
        *,
        event: str,
        stall: StallDetectionResult,
        strong_recovery: bool,
    ) -> None:
        logger.info(
            "birth.%s stage=%s winrate_velocity=%.6f reward_velocity=%.6f "
            "combined=%.6f attempts=%s/%s strong_recovery=%s escalation=%s",
            event,
            self.stage.value,
            stall.winrate_velocity,
            stall.reward_velocity,
            stall.combined_velocity,
            stall.low_velocity_attempts,
            stall.threshold,
            strong_recovery,
            self.escalation_level,
        )

    def _log_provisional_pass_outcome(self, 
        *,
        source: str,
        should_grant: bool,
        blocked_reason: str | None,
        safeguards: dict[str, Any],
    ) -> None:
        logger.info(
            "birth.provisional_pass source=%s stage=%s should_grant=%s "
            "blocked_reason=%s safeguards=%s",
            source,
            self.stage.value,
            should_grant,
            blocked_reason or "",
            safeguards,
        )

    def _apply_meta_plan(self, plan: MetaActionPlan, *, trigger: str = "") -> None:
        self.meta_last_plan = plan
        if plan.escalation_delta > 0:
            self.escalation_level = min(
                self.cur_cfg.max_escalation_level,
                self.escalation_level + plan.escalation_delta,
            )
        elif plan.escalation_delta < 0:
            self.escalation_level = max(0, self.escalation_level + plan.escalation_delta)
        if plan.chunk_target is not None:
            self.cur_cfg.rollout_chunk_trades = plan.chunk_target
        if plan.enter_strong_recovery:
            self.strong_recovery_mode = True
            self.strong_recovery_attempts = 0
            self.low_velocity_attempts = 0
            self.bus.meta_patch_state(
                self.stage,
                explore_multiplier=max(
                    0.4,
                    min(1.0, float(self.cur_cfg.meta_explore_decay_stall)),
                ),
            )
        if plan.exit_strong_recovery:
            self.strong_recovery_mode = False
            self.strong_recovery_attempts = 0
            self.cur_cfg.rollout_chunk_trades = max(
                self.cur_cfg.exploration_chunk_size,
                self.original_rollout_chunk,
            )
            self.bus.meta_patch_state(self.stage, explore_multiplier=1.0)
        if plan.explore_steps_multiplier != 1.0:
            self.bus.meta_patch_state(
                self.stage,
                explore_multiplier=max(
                    0.4,
                    min(1.0, float(plan.explore_steps_multiplier)),
                ),
            )
        if plan.intra_hard_pct_delta is not None and self.intra_state is not None:
            self.intra_state.hard_pct = max(
                self.cur_cfg.intra_initial_hard_pct,
                min(
                    self.cur_cfg.intra_max_hard_pct,
                    self.intra_state.hard_pct + plan.intra_hard_pct_delta,
                ),
            )
        if plan.mine:
            self._mine_and_inject(aggressive=plan.mine_aggressive)
        if plan.expand_data:
            self._maybe_expand_data()
        if plan.reward_tweak is not None:
            self.bus.meta_patch_state(self.stage, active_reward=reward_config_to_dict(plan.reward_tweak))
        if plan.primary != RecoveryStrategy.HOLD:
            self.meta_message_suffix = (
                f" · meta: {plan.primary.value} ({plan.rationale})"
            )
        self_eval_suffix = self.bus.meta_format_self_eval_suffix(self.stage)
        if self_eval_suffix:
            self.meta_message_suffix = self_eval_suffix
        if trigger:
            self._log_meta_decision(plan, trigger)
        else:
            logger.info(
                "birth.meta.applied primary=%s rationale=%s",
                plan.primary.value,
                plan.rationale,
            )

