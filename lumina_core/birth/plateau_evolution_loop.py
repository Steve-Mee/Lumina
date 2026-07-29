"""Plateau evolution step finalize / advance / detect / terminal helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    EvolutionAction,
    PlateauEnterContext,
    begin_evolution_step,
    evolution_ladder_exhausted,
    is_plateau_quarantine_blocking,
    maybe_update_best_winrate,
    record_evolution_outcome,
    revert_evolution_step_on_noop,
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
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class PlateauEvolutionLoopMixin(StageLoopMixinBase):
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
        if not evolution_ladder_exhausted(
            self.plateau_state,
            stage=self.stage,
            max_steps=self._evolution_max_steps(),
        ):
            return False
        # Starship gap-fill: after freeze/accept, no stall-remediation theater.
        from lumina_core.birth.birth_control_plane import should_skip_plateau_ladder_theater

        if should_skip_plateau_ladder_theater(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
        ):
            rejected = bool(
                getattr(self.swarm_state, "rejected_no_lift", False)
                or getattr(self, "swarm_rejected_no_lift", False)
            ) and not bool(
                getattr(self, "swarm_champion_accepted", False)
                or getattr(self.swarm_state, "champion_accepted", False)
            )
            if rejected:
                self._write_progress(
                    phase="swarm_reject_attention",
                    message=(
                        "Swarm tournament produced no tournament lift — "
                        "champion frozen; accept champion or wipe."
                    ),
                )
            return False
        # Starship A4: stall remediation only after swarm tournament finished.
        if bool(getattr(self.cur_cfg, "starship_stall_after_swarm_only", True)):
            if self._ensure_swarm_first() or bool(self.swarm_state.active):
                return True
            if not str(getattr(self.swarm_state, "committed_variant_id", "") or "").strip():
                if self._ensure_swarm_first() or bool(self.swarm_state.active):
                    return True
        pending = self._plateau_terminal_pending(failure_key=failure_key)
        if pending is None:
            return False
        return self._try_stall_remediation_on_terminal(pending)

    def _maybe_advance_plateau_evolution_in_loop(self) -> bool:
        """Advance plateau evolution between rollouts (mirrors remediation loop)."""
        if not self.plateau_state.active or self.allow_provisional:
            return False
        from lumina_core.birth.birth_control_plane import should_skip_plateau_ladder_theater

        if should_skip_plateau_ladder_theater(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
        ):
            # Starship B4: after freeze/accept, burn ladder to terminal without theater.
            self.plateau_state.evolution_step = max(
                int(self.plateau_state.evolution_step),
                int(self._evolution_max_steps()),
            )
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
            stage_trades=self.stage_trades,
            required=self.required,
        )
        if not should_trigger_plateau_evolution_step(
            self.plateau_state,
            cfg=self.cur_cfg,
            current_winrate=current_winrate,
            allow_start=False,
            pass_target=pass_target,
            ppo_steps_since_step_start=ppo_since,
            stage_trades=self.stage_trades,
            required=self.required,
        ):
            return False
        if self._maybe_entropy_life_support():
            return True
        if bool(self.swarm_state.active):
            # Swarm-first: finish tournament before ladder steps.
            return False
        action = begin_evolution_step(
            self.plateau_state,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            stage=self.stage,
            max_steps=self._evolution_max_steps(),
        )
        if action == EvolutionAction.TERMINAL:
            return False
        detail, applied = self._apply_plateau_evolution_action(action)
        self._finalize_plateau_evolution_step(
            action=action,
            detail=detail,
            failure_key=self._stage_failure_key(),
            applied=applied,
            forced_advance=forced,
        )
        return applied or forced

    def _stage_failure_key(self) -> str:
        return {
            CurriculumStage.STAGE1_TREND: "stage1_winrate",
            CurriculumStage.STAGE2_RANGE: "stage2_metric",
            CurriculumStage.STAGE3_MIXED: "stage3_foundation",
        }.get(self.stage, "stage_metrics")

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
        meta_health = str(getattr(self, "meta_learning_health", "") or "")
        if not meta_health and self.cur_cfg.meta_controller_enabled:
            try:
                snap = getattr(self, "meta_last_plan", None)
                if snap is not None and getattr(snap, "snapshot", None) is not None:
                    meta_health = str(
                        getattr(snap.snapshot.learning_health, "value", "")
                        or snap.snapshot.learning_health
                        or ""
                    )
            except Exception:
                meta_health = ""
        winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        hygiene = float(getattr(self.cur_cfg, "stage1_winrate_pass_floor", 0.35) or 0.35)
        if self.stage == CurriculumStage.STAGE3_MIXED:
            hygiene = float(getattr(self.cur_cfg, "stage3_winrate_floor", 0.35) or 0.35)
        skill_failing = winrate + 1e-9 < hygiene
        if self.bus.plateau_check_enter(
            self.stage,
            stage_trades=ctx.stage_trades,
            stage_wins=ctx.stage_wins,
            required=ctx.required,
            winrate_trend_slope=ctx.winrate_trend_slope,
            velocity_stall_attempts=ctx.velocity_stall_attempts,
            meta_self_eval_phase=ctx.meta_self_eval_phase,
            pass_metric_target=ctx.pass_metric_target,
            plateau_quarantine_active=ctx.plateau_quarantine_active,
            wall_budget_exhausted=bool(getattr(self, "wall_budget_exhausted", False)),
            meta_learning_health=meta_health,
            skill_failing=skill_failing,
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
            # Starship A3: swarm tournament first; ladder waits until swarm idle.
            self._start_policy_swarm(force=False)
            if not bool(self.swarm_state.active):
                self._try_plateau_evolution(failure_key=self._stage_failure_key())

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
            policy_entropy=self._resolve_policy_entropy(),
            ppo_steps=int(getattr(self.host, "ppo_steps", 0) or 0),
        )
        # Always populate metric keys (Raptor v9 — no KeyError in finalize).
        if not blocker_metric:
            blocker_metric = "plateau_evolution_exhausted"
            blocker_value = float(self.plateau_state.evolution_step)
            blocker_reason = TERMINAL_STALL_REASON
        return {
            "failure_key": failure_key,
            "blocker_metric": blocker_metric,
            "blocker_value": blocker_value if blocker_value is not None else 0.0,
            "blocker_reason": blocker_reason or TERMINAL_STALL_REASON,
            "terminal_stall_reason": TERMINAL_STALL_REASON,
        }

    def _try_plateau_evolution(self, *, failure_key: str) -> bool:
        if not self.plateau_state.active or self.allow_provisional:
            return False
        from lumina_core.birth.birth_control_plane import should_skip_plateau_ladder_theater

        if should_skip_plateau_ladder_theater(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
        ):
            self.plateau_state.evolution_step = max(
                int(self.plateau_state.evolution_step),
                int(self._evolution_max_steps()),
            )
            return False
        if self._maybe_entropy_life_support():
            return True
        if bool(self.swarm_state.active):
            return False
        if bool(getattr(self.cur_cfg, "starship_swarm_first_enabled", True)):
            if self._ensure_swarm_first():
                return True
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
            stage=self.stage,
            max_steps=self._evolution_max_steps(),
        )
        if action == EvolutionAction.TERMINAL:
            return False
        detail, applied = self._apply_plateau_evolution_action(action)
        self._finalize_plateau_evolution_step(
            action=action,
            detail=detail,
            failure_key=failure_key or self._stage_failure_key(),
            applied=applied,
            forced_advance=forced,
        )
        return applied or forced

    def _maybe_save_best_policy(self, *, stage_trades: int, stage_wins: int) -> None:
        snapshot_path = self._best_policy_snapshot_path()
        roll_wr: float | None = None
        roll_src: str | None = None
        try:
            roll_wr, roll_src, _cov = self._rolling_winrate_meta()
        except Exception:
            pass
        if maybe_update_best_winrate(
            self.plateau_state,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            policy_path=str(snapshot_path),
            cfg=self.cur_cfg,
            rolling_winrate=roll_wr,
            rolling_source=roll_src,
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
