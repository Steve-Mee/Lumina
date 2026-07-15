"""PlateauEvolutionMixin — StageLoopSession mixin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    EvolutionAction,
    PlateauEnterContext,
    begin_evolution_step,
    evolution_ladder_exhausted,
    is_plateau_quarantine_blocking,
    is_valid_best_policy_snapshot,
    maybe_update_best_winrate,
    record_evolution_outcome,
    revert_evolution_step_on_noop,
    rolling_winrate_last_n_trades,
    sanitize_plateau_best_snapshot,
    should_force_advance_evolution_step,
    should_terminal_plateau_stall,
    should_trigger_plateau_evolution_step,
)
from lumina_core.birth.stage_scorecard import (
    calculate_simple_slope,
    compute_stage_blocker,
    learning_metric_target,
)
from lumina_core.birth.stall_remediation import (
    curate_buffer_top_quartile,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")

class PlateauEvolutionMixin(StageLoopMixinBase):
    """See StageLoopSession for attributes."""

    def _rolling_winrate_500(self) -> float:
        return rolling_winrate_last_n_trades(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            wins_at_trade=self.wins_at_trade_milestones,
        )

    def _ppo_steps_since_evolution_step(self) -> int:
        return max(0, int(self.host.ppo_steps) - int(self.ppo_steps_at_plateau_evolution_step))

    def _apply_plateau_evolution_action(self, action: EvolutionAction) -> tuple[str, bool]:
        if action == EvolutionAction.EXPAND_DATA:
            if not self.cur_cfg.auto_expand_on_adaptation:
                return "expand skipped — auto_expand_on_adaptation disabled", False
            if self._maybe_expand_data():
                return "expanded data window", True
            return "expand skipped — data window at max", False
        if action == EvolutionAction.POLICY_ROLLBACK:
            if not is_valid_best_policy_snapshot(self.plateau_state, cfg=self.cur_cfg):
                return "rollback skipped — no valid best policy snapshot (min trades)", False
            rollback_path = str(self.plateau_state.best_policy_path or "").strip()
            if rollback_path and Path(rollback_path).is_file():
                self.host.current_policy = self.host._create_birth_policy(
                    allow_load_existing=True,
                    policy_path=rollback_path,
                )
                return f"rollback to {self.plateau_state.best_winrate:.1%} winrate", True
            return "rollback skipped — no best policy snapshot", False
        if action == EvolutionAction.INTRA_EASY_ONLY:
            if self.intra_state is not None:
                self.intra_state.hard_pct = 0.0
                self.intra_state.easy_trades = 0
                self.intra_state.easy_wins = 0
                self.intra_state.easy_winrate_history.clear()
                self._rebuild_intra_pools(self.active_stage_ticks)
                return "intra stage1 easy-only pool", True
            return "intra easy-only skipped — not stage1", False
        if action == EvolutionAction.FRESH_POLICY:
            self.host.current_policy = self.host._create_birth_policy(
                allow_load_existing=False,
                force_reinit=True,
            )
            return "fresh policy (reinitialized weights, buffer/oracle retained)", True
        if action == EvolutionAction.ORACLE_DISTILL:
            return self._apply_oracle_distill(), True
        if action == EvolutionAction.PHOENIX_RESET:
            return self._apply_phoenix_reset()
        return "", False

    def _finalize_plateau_evolution_step(self, 
        *,
        action: EvolutionAction,
        detail: str,
        failure_key: str,
        applied: bool = True,
        forced_advance: bool = False,
    ) -> None:
        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        self.evolution_last_action_applied = bool(applied or forced_advance)
        self.evolution_last_action_detail = str(detail or "")
        if not applied and not forced_advance:
            revert_evolution_step_on_noop(self.plateau_state)
            self.plateau_state.evolution_noop_count += 1
            logger.info(
                "birth.plateau.evolution_noop step=%s action=%s detail=%s noops=%s",
                self.plateau_state.evolution_step,
                action.value,
                detail,
                self.plateau_state.evolution_noop_count,
            )
            self._write_progress(
                phase="plateau_evolution",
                message=(
                    f"Plateau evolution skipped (no-op): {detail} "
                    f"· noops {self.plateau_state.evolution_noop_count}/"
                    f"{self.cur_cfg.plateau_evolution_max_noops_per_step}"
                ),
            )
            return
        if not applied and forced_advance:
            detail = f"{detail} (forced advance after no-ops)"
        self.plateau_state.evolution_noop_count = 0
        self.ppo_steps_at_plateau_evolution_step = int(self.host.ppo_steps)
        record_evolution_outcome(
            self.plateau_state,
            action=action,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            detail=detail,
            applied=applied,
            rolling_winrate_500=self._rolling_winrate_500(),
        )
        self.attempt = 0
        self.host._persist_checkpoint(
            training_mode=self.training_mode,
            curriculum_stage=self.stage.value,
            policy_path=str(self.host.final_policy_path),
            phase="plateau_evolution",
            stage_metrics=self._stage_metrics_payload(),
        )
        forced_suffix = " (forced advance)" if forced_advance else ""
        self._write_progress(
            phase="plateau_evolution",
            message=(
                f"Plateau evolution step {self.plateau_state.evolution_step}/"
                f"{self.cur_cfg.plateau_max_evolution_steps}: {detail}{forced_suffix}"
            ),
        )
        logger.info(
            "birth.plateau.evolution_applied step=%s action=%s detail=%s failure=%s forced=%s",
            self.plateau_state.evolution_step,
            action.value,
            detail,
            failure_key,
            forced_advance,
        )
        try:
            from lumina_core.notifications.milestone_events import plateau_evolution_step_event

            self.host._notify_milestone(
                plateau_evolution_step_event(
                    step=self.plateau_state.evolution_step,
                    max_steps=int(self.cur_cfg.plateau_max_evolution_steps),
                    action=action.value,
                    detail=f"{detail}{forced_suffix}",
                    winrate=current_winrate,
                )
            )
        except Exception as exc:
            logger.debug("birth.milestone_evolution_notify_failed: %s", exc)
        if forced_advance:
            try:
                from lumina_core.notifications.milestone_events import (
                    plateau_evolution_forced_advance_event,
                )

                self.host._notify_milestone(
                    plateau_evolution_forced_advance_event(
                        step=self.plateau_state.evolution_step,
                        max_steps=int(self.cur_cfg.plateau_max_evolution_steps),
                        action=action.value,
                        winrate=current_winrate,
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_forced_advance_notify_failed: %s", exc)

    def _plateau_pass_target(self) -> float:
        return learning_metric_target(
            self.stage,
            cfg=self.cur_cfg,
            pass_criteria=self.stage_pass_criteria,
        )

    def _try_evolution_exhausted_remediation(self, *, failure_key: str) -> bool:
        """Start stall remediation when evolution ladder is done (no phantom steps)."""
        if not self.plateau_state.active or self.allow_provisional:
            return False
        if not evolution_ladder_exhausted(self.plateau_state):
            return False
        pending = self._plateau_terminal_pending(failure_key=failure_key)
        if pending is None:
            return False
        return self._try_stall_remediation_on_terminal(pending)

    def _maybe_advance_plateau_evolution_in_loop(self) -> bool:
        """Advance plateau evolution between rollouts (mirrors remediation loop)."""
        if not self.plateau_state.active or self.allow_provisional:
            return False
        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        pass_target = self._plateau_pass_target()
        ppo_since = self._ppo_steps_since_evolution_step()
        forced = should_force_advance_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        )
        if not should_trigger_plateau_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            allow_start=False,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        ):
            return False
        action = begin_evolution_step(
            self.plateau_state,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
        )
        if action == EvolutionAction.TERMINAL:
            return False
        detail, applied = self._apply_plateau_evolution_action(action)
        self._finalize_plateau_evolution_step(
            action=action,
            detail=detail,
            failure_key="stage1_winrate",
            applied=applied,
            forced_advance=forced,
        )
        return applied or forced

    def _maybe_detect_plateau(self, *, stage_trades: int, stage_wins: int) -> None:
        if self.plateau_state.active or self.allow_provisional:
            return
        ctx = PlateauEnterContext(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            required=self.required,
            winrate_trend_slope=calculate_simple_slope(self.winrate_history),
            velocity_stall_attempts=self.low_velocity_attempts,
            meta_self_eval_phase=self._meta_self_eval_phase_str(),
            pass_metric_target=self.pass_metric_target,
            plateau_quarantine_active=is_plateau_quarantine_blocking(
                quarantine_rollouts_remaining=int(
                    self.plateau_quarantine.get("plateau_quarantine_rollouts_remaining", 0) or 0
                ),
                quarantine_trades_at_resume=int(
                    self.plateau_quarantine.get("plateau_quarantine_trades_at_resume", 0) or 0
                ),
                stage_trades=self.stage_trades,
                quarantine_min_trades=int(
                    self.plateau_quarantine.get("plateau_quarantine_trades_remaining", 0)
                    or self.cur_cfg.plateau_quarantine_min_trades
                ),
            ),
            stage=self.stage,
        )
        if self.bus.plateau_check_enter(
            self.stage,
            stage_trades=ctx.stage_trades,
            stage_wins=ctx.stage_wins,
            required=ctx.required,
            winrate_trend_slope=ctx.winrate_trend_slope,
            velocity_stall_attempts=ctx.velocity_stall_attempts,
            meta_self_eval_phase=ctx.meta_self_eval_phase,
            range_flat_ratio=float(self.stage_range_flat_bars)
            / float(max(1, self.stage_range_total_signals)),
            range_round_trips=self.stage_range_round_trips,
            velocity_stall=self.low_velocity_attempts > 0,
        ):
            self.bus.plateau_enter(self.stage, stage_trades=self.stage_trades, stage_wins=self.stage_wins)
            self.ppo_steps_at_plateau_evolution_step = int(self.host.ppo_steps)
            sanitize_plateau_best_snapshot(
                self.plateau_state,
                cfg=self.cur_cfg,
                stage_trades=self.stage_trades,
                stage_wins=self.stage_wins,
            )
            wr = float(self.stage_wins) / float(max(1, self.stage_trades))
            try:
                from lumina_core.notifications.milestone_events import plateau_entered_event

                self.host._notify_milestone(
                    plateau_entered_event(
                        stage_trades=self.stage_trades,
                        winrate=wr,
                        pass_target=self.pass_metric_target,
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_plateau_enter_failed: %s", exc)
            self._start_policy_swarm()
            self._try_plateau_evolution(failure_key="stage1_winrate")

    def _plateau_terminal_pending(self, *, failure_key: str) -> dict[str, Any] | None:
        if not should_terminal_plateau_stall(
            self.plateau_state,
            stage_trades=self.stage_trades,
            required=self.required,
            cfg=self.cur_cfg,
            meta_self_eval_phase=self._meta_self_eval_phase_str(),
            remediation_exhausted=self._remediation_exhausted_now(),
            trade_budget_remaining=self._trade_budget_remaining(),
        ):
            return None
        hold_ratio = float(self.stage_hold_signals) / float(max(1, self.stage_total_signals))
        range_flat_ratio = float(self.stage_range_flat_bars) / float(max(1, self.stage_range_total_signals))
        blocker_metric, blocker_value, blocker_reason = compute_stage_blocker(
            self.stage,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            hold_ratio=hold_ratio,
            required=self.required,
            constitution_violations=self.host._constitution_guard.violations,
            range_flat_ratio=range_flat_ratio,
            range_round_trips=self.stage_range_round_trips,
            range_total_signals=self.stage_range_total_signals,
            cfg=self.cur_cfg,
        )
        return {
            "failure_key": failure_key,
            "blocker_metric": blocker_metric,
            "blocker_value": blocker_value,
            "blocker_reason": TERMINAL_STALL_REASON,
            "terminal_stall_reason": TERMINAL_STALL_REASON,
        }

    def _try_plateau_evolution(self, *, failure_key: str) -> bool:
        if not self.plateau_state.active or self.allow_provisional:
            return False
        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        pass_target = self._plateau_pass_target()
        ppo_since = self._ppo_steps_since_evolution_step()
        forced = should_force_advance_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        )
        if not should_trigger_plateau_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            allow_start=True,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
        ):
            return False
        action = begin_evolution_step(
            self.plateau_state,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
        )
        if action == EvolutionAction.TERMINAL:
            return False
        detail, applied = self._apply_plateau_evolution_action(action)
        self._finalize_plateau_evolution_step(
            action=action,
            detail=detail,
            failure_key=failure_key,
            applied=applied,
            forced_advance=forced,
        )
        return applied or forced

    def _maybe_save_best_policy(self, *, stage_trades: int, stage_wins: int) -> None:
        snapshot_path = self._best_policy_snapshot_path()
        if maybe_update_best_winrate(
            self.plateau_state,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            policy_path=str(snapshot_path),
            cfg=self.cur_cfg,
        ):
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            save_fn = getattr(self.host.ppo_trainer, "save_final_birth_policy", None)
            if callable(save_fn):
                save_fn(str(snapshot_path))
                logger.info(
                    "birth.plateau.best_policy_saved path=%s winrate=%.2f%% trades=%s",
                    snapshot_path,
                    self.plateau_state.best_winrate * 100.0,
                    self.stage_trades,
                )
                try:
                    from lumina_core.notifications.milestone_events import (
                        best_policy_updated_event,
                    )

                    self.host._notify_milestone(
                        best_policy_updated_event(
                            winrate=self.plateau_state.best_winrate,
                            stage_trades=self.stage_trades,
                            policy_path=str(snapshot_path),
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_best_policy_failed: %s", exc)

    def _best_policy_snapshot_path(self) -> Path:
        return self.host.workspace_root / "lumina_agents" / "ppo" / f"birth_best_{self.stage.value}.zip"

    def _meta_self_eval_phase_str(self) -> str:
        if self.cur_cfg.meta_controller_enabled and self.cur_cfg.meta_self_eval_enabled:
            return str(self.bus.meta_self_eval_state(self.stage).get('phase', ''))
        return ""

    def _apply_phoenix_reset(self) -> tuple[str, bool]:
        self.host.current_policy = self.host._create_birth_policy(
            allow_load_existing=False,
            force_reinit=True,
        )
        removed = curate_buffer_top_quartile(
            self.host.buffer,
            keep_pct=float(self.cur_cfg.plateau_oracle_distill_top_pct),
        )
        if self.intra_state is not None:
            self.intra_state.hard_pct = 0.0
            self.intra_state.easy_trades = 0
            self.intra_state.easy_wins = 0
            self.intra_state.easy_winrate_history.clear()
            self._rebuild_intra_pools(self.active_stage_ticks)
        self.escalation_level = min(self.cur_cfg.max_escalation_level, self.escalation_level + 2)
        self.strong_recovery_mode = True
        detail = f"phoenix reset (policy reinit, buffer curated, removed {removed})"
        try:
            from lumina_core.notifications.milestone_events import phoenix_reset_event

            self.host._notify_milestone(
                phoenix_reset_event(
                    cycle=self.plateau_state.full_recovery_cycles,
                    winrate=float(self.stage_wins) / float(max(1, self.stage_trades)),
                    detail=detail,
                )
            )
        except Exception as exc:
            logger.debug("birth.milestone_phoenix_failed: %s", exc)
        return detail, True

    def _effective_max_rollouts(self) -> int:
        if not self.plateau_state.active and not self.remediation_state.active:
            if self.allow_provisional:
                return self.max_rollouts
            return self.max_rollouts
        if self.allow_provisional:
            return self.max_rollouts
        if self.remediation_state.active:
            return min(self.max_rollouts, self.cur_cfg.stall_remediation_rollouts_per_step)
        if (
            self.plateau_state.evolution_step > 0
            or self.plateau_state.active
        ):
            return min(self.max_rollouts, self.cur_cfg.plateau_evolution_rollouts_per_step)
        return self.max_rollouts

