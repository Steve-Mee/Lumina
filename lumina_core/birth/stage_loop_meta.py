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


def _observe_median_loss_r(loop: Any) -> float | None:
    series = list(getattr(loop, "stage_val_r", None) or [])
    if not series:
        return None
    from lumina_core.birth.foundation_metrics import median_loss_r

    return median_loss_r(series)


class StageLoopMetaMixin(StageLoopMixinBase):
    """See StageLoopSession for attributes."""

    def _observe_snapshot(self) -> tuple[Any, StallDetectionResult]:
        rolling_wr = None
        try:
            rolling_wr, _, _ = self._rolling_winrate_meta()
        except Exception:
            rolling_wr = None
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
            range_total_signals=int(self.stage_range_total_signals),
            plateau_active=bool(getattr(self.plateau_state, "active", False)),
            expectancy_quality_step=int(getattr(self, "expectancy_quality_step", 0) or 0),
            stage_wins=int(self.stage_wins),
            rolling_winrate=rolling_wr,
            volume_gate_passed=int(self.stage_trades) >= int(self.required),
            edge_vs_random=(
                float(getattr(self, "_edge_vs_random"))
                if getattr(self, "_edge_vs_random", None) is not None
                else None
            ),
            median_loss_r=_observe_median_loss_r(self),
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
        # Hard choke-point: Stage-2 expectancy stall never applies explore thrash.
        coerced_flag = False
        stall_flag: bool | None = None
        try:
            from lumina_core.birth.expectancy_stall import (
                coerce_meta_plan_under_expectancy_quality,
                loop_expectancy_stall,
                plan_is_expectancy_thrash,
            )
            from lumina_core.birth.runtime_diagnostics import log_meta_decision_trace

            stall_flag = bool(loop_expectancy_stall(self, cfg=self.cur_cfg))
            if stall_flag:
                coerced = coerce_meta_plan_under_expectancy_quality(
                    plan,
                    loop=self,
                    snap=getattr(plan, "snapshot", None),
                    cfg=self.cur_cfg,
                    exploration_steps=int(self.cur_cfg.exploration_steps),
                    strong_recovery_explore_fraction=float(
                        self.cur_cfg.strong_recovery_explore_fraction
                    ),
                )
                if coerced is not plan and (
                    plan_is_expectancy_thrash(plan)
                    or str(getattr(plan.primary, "value", plan.primary)) == "explore_boost"
                    or "declining_pattern_focus_explore"
                    in str(getattr(plan, "rationale", "") or "")
                ):
                    logger.warning(
                        "birth.meta.apply_coerce trigger=%s from=%s/%s to=%s/%s",
                        trigger,
                        getattr(plan.primary, "value", plan.primary),
                        plan.rationale,
                        getattr(coerced.primary, "value", coerced.primary),
                        getattr(coerced, "rationale", ""),
                    )
                    plan = coerced  # type: ignore[assignment]
                    coerced_flag = True
            log_meta_decision_trace(
                trigger=str(trigger or "apply"),
                primary=str(getattr(plan.primary, "value", plan.primary)),
                rationale=str(getattr(plan, "rationale", "") or ""),
                secondary=[
                    str(getattr(s, "value", s)) for s in (getattr(plan, "secondary", ()) or ())
                ],
                stage=str(getattr(self.stage, "value", self.stage)),
                stage_trades=int(getattr(self, "stage_trades", 0) or 0),
                stage_wins=int(getattr(self, "stage_wins", 0) or 0),
                flat=float(getattr(self, "stage_range_flat_bars", 0) or 0)
                / float(max(1, int(getattr(self, "stage_range_total_signals", 0) or 0))),
                stall=stall_flag,
                coerced=coerced_flag,
                source="apply_meta_plan",
            )
        except Exception as exc:
            logger.warning("birth.meta.apply_coerce_failed: %s", exc)

        self.meta_last_plan = plan
        # Advance Stage-2 expectancy quality ladder when quality owns recovery.
        rationale = str(getattr(plan, "rationale", "") or "")
        if "stage2_expectancy" in rationale.lower() or "expectancy_quality" in rationale.lower():
            # Only count real quality applications (not double-count plateau defer).
            self.expectancy_quality_step = int(
                getattr(self, "expectancy_quality_step", 0) or 0
            ) + 1
            self.expectancy_quality_step_source = "meta_apply"
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
            # PR-H gap: finish / near-miss / peak_grad — no inject flood.
            skip_mine = False
            try:
                from lumina_core.birth.stage2_peak_capture import (
                    finish_mode_blocks_pattern_inject,
                )

                peak_st = getattr(self, "stage2_peak_state", None)
                if peak_st is not None and finish_mode_blocks_pattern_inject(peak_st):
                    skip_mine = True
                    logger.info(
                        "birth.meta.mine_skipped_finish_mode peak_grad=%s near_miss=%s",
                        bool(getattr(peak_st, "peak_grad_armed", False)),
                        bool(getattr(peak_st, "near_miss_active", False)),
                    )
            except Exception:
                skip_mine = False
            if not skip_mine:
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

