"""Phoenix in-loop + stall remediation advancement (stage-loop recovery)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import filter_ticks_for_stage
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    reset_plateau_for_new_cycle,
    should_block_phoenix_no_lift,
    should_brake_recovery_no_lift,
    should_phoenix_reset,
)
from lumina_core.birth.remediation import filter_train_ticks_for_holdout_profile
from lumina_core.birth.stall_remediation import (
    HUMAN_GATE_REASON,
    StallRemediationAction,
    curate_buffer_bottom_half,
)
from lumina_core.birth.starship_birth import should_block_phoenix_until_swarm
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_recovery_remediation")


class StageLoopRecoveryRemediationMixin(StageLoopMixinBase):
    """Phoenix novelty and stall remediation step/cycle orchestration."""

    def _apply_phoenix_in_loop(self, *, stall_reason: str) -> bool:
        """Apply phoenix novelty inside rollout loop; True when loop should continue."""
        if not self.cur_cfg.autonomous_recovery_enabled or not self.cur_cfg.phoenix_loop_enabled:
            return False
        if bool(getattr(self.swarm_state, "rejected_no_lift", False)) or bool(
            getattr(self, "swarm_rejected_no_lift", False)
        ):
            logger.warning(
                "birth.phoenix.blocked_swarm_rejected_no_lift stall=%s",
                stall_reason,
            )
            self._write_progress(
                phase="stage_stalled",
                message=(
                    "Starship: swarm rejected (no tournament lift) — phoenix blocked; "
                    "champion frozen"
                ),
            )
            return False
        if should_brake_recovery_no_lift(self.plateau_state) or should_block_phoenix_no_lift(
            self.plateau_state
        ):
            logger.warning(
                "birth.phoenix.in_loop blocked_no_lift cycles=%s best=%.2f%%",
                self.plateau_state.full_recovery_cycles,
                float(self.plateau_state.best_winrate) * 100.0,
            )
            # Starship A3: no-lift → force swarm tournament once, never silent phoenix spam.
            if self._ensure_swarm_first() or bool(self.swarm_state.active):
                return True
            self.swarm_rejected_no_lift = True
            self._write_progress(
                phase="stage_stalled",
                message=(
                    "Starship no-lift brake: swarm tournament required before phoenix; "
                    "needs attention"
                ),
            )
            return False
        if should_block_phoenix_until_swarm(
            cfg=self.cur_cfg,
            swarm_state=self.swarm_state,
            allow_provisional=self.allow_provisional,
        ):
            if self._ensure_swarm_first() or bool(self.swarm_state.active):
                logger.info("birth.phoenix.blocked_swarm_first stall=%s", stall_reason)
                return True
            logger.warning("birth.phoenix.blocked_awaiting_swarm stall=%s", stall_reason)
            return False
        if self._maybe_entropy_life_support():
            return True
        patch = self.bus.phoenix_begin_cycle(
            self.stage,
            stall_reason=stall_reason,
            novelty=str(self.organism_autonomy_state.phoenix.last_action or "expand_data"),
        )
        if patch is None:
            return False
        self.organism_autonomy_state.autonomous_recovery_count += 1
        self.remediation_state.active = False
        self.remediation_state.remediation_step = 0
        self.remediation_state.remediation_rollouts_this_step = 0
        _cid = self.bus.emit(
            "plateau_reset_cycle",
            self.stage,
            {"stage_trades": self.stage_trades, "stage_wins": self.stage_wins},
        )
        self.bus.registry.pop_response(_cid)
        novelty_value = str(self.organism_autonomy_state.phoenix.last_action or "expand_data")
        detail = f"phoenix in-loop: {novelty_value}"
        if novelty_value in {"expand_data", "widen_horizon"}:
            self._maybe_expand_data()
            detail = f"{detail}; data expanded"
        elif novelty_value == "policy_swarm":
            self._start_policy_swarm()
            detail = f"{detail}; policy swarm started"
        elif novelty_value == "reward_sweep":
            self.remediation_state.meta_sweep_index += 1
            self.escalation_level = min(self.cur_cfg.max_escalation_level, self.escalation_level + 1)
            detail = f"{detail}; reward sweep #{self.remediation_state.meta_sweep_index}"
        elif novelty_value == "soft_gate":
            detail = f"{detail}; soft gate floor {self.cur_cfg.stage1_winrate_pass_floor:.0%}"
        self.attempt = 0
        self.strong_recovery_mode = True
        self._write_progress(phase="phoenix_cycle", message=detail)
        logger.warning("birth.phoenix.in_loop %s", detail)
        return True

    def _apply_stall_remediation_action(self, action: StallRemediationAction | None) -> str:
        if action is None:
            return "no action"
        if self._maybe_entropy_life_support():
            return "starship exploration burst (entropy life-support)"
        detail = ""
        if action == StallRemediationAction.EXPAND_AND_RETRY:
            self._maybe_expand_data()
            detail = "expanded data window"
        elif action == StallRemediationAction.BUFFER_CURATE_ORACLE:
            removed = curate_buffer_bottom_half(self.host.buffer)
            self.strong_recovery_mode = True
            self._mine_and_inject(aggressive=True)
            detail = f"curated {removed} low-reward buffer trajectories"
        elif action == StallRemediationAction.REGIME_DIVERSE_SLICE:
            filtered = filter_train_ticks_for_holdout_profile(
                self.active_train,
                self.holdout_ticks_ref,
            )
            if filtered:
                self.active_train = list(filtered)
                self.active_stage_ticks = filter_ticks_for_stage(self.stage, self.active_train)
            detail = "regime-diverse train slice applied"
        elif action == StallRemediationAction.META_SWEEP:
            self.remediation_state.meta_sweep_index += 1
            self.escalation_level = min(
                self.cur_cfg.max_escalation_level,
                self.escalation_level + 1,
            )
            detail = f"meta explore sweep #{self.remediation_state.meta_sweep_index}"
        elif action == StallRemediationAction.ORACLE_DISTILL:
            detail = self._apply_oracle_distill()
        if self.remediation_state.remediation_cycle >= 2:
            freeze_armed = bool(
                getattr(self.cur_cfg, "starship_champion_freeze_enabled", True)
            ) and not bool(self.allow_provisional)
            rejected = bool(getattr(self.swarm_state, "rejected_no_lift", False)) or bool(
                getattr(self, "swarm_rejected_no_lift", False)
            )
            champ_path = str(
                getattr(self, "best_edgescore_policy_path", "")
                or getattr(self.plateau_state, "best_policy_path", "")
                or ""
            ).strip()
            if rejected or (freeze_armed and champ_path):
                if detail:
                    detail = (
                        f"{detail}; reinit skipped (champion freeze) "
                        f"cycle {self.remediation_state.remediation_cycle}"
                    )
                else:
                    detail = (
                        f"reinit skipped (champion freeze) "
                        f"cycle {self.remediation_state.remediation_cycle}"
                    )
            else:
                self.host.current_policy = self.host._create_birth_policy(
                    allow_load_existing=False
                )
                if self.intra_state is not None:
                    self.intra_state.hard_pct = 0.0
                    self._rebuild_intra_pools(self.active_stage_ticks)
                self.strong_recovery_mode = True
                if detail:
                    detail = (
                        f"{detail}; aggressive cycle {self.remediation_state.remediation_cycle}"
                    )
                else:
                    detail = f"aggressive cycle {self.remediation_state.remediation_cycle}"
        return detail

    def _try_stall_remediation_on_terminal(self, pending: dict[str, Any]) -> bool:
        """Return True when remediation applied and loop should continue."""
        stall_reason = str(
            pending.get("terminal_stall_reason") or pending.get("blocker_reason") or ""
        )
        if stall_reason != TERMINAL_STALL_REASON:
            return False
        from lumina_core.birth.birth_control_plane import should_skip_plateau_ladder_theater

        if should_skip_plateau_ladder_theater(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
        ):
            logger.info(
                "birth.stall_remediation.skipped_after_swarm_freeze reject=%s accept=%s",
                bool(getattr(self, "swarm_rejected_no_lift", False)),
                bool(getattr(self, "swarm_champion_accepted", False)),
            )
            return False
        if self._maybe_entropy_life_support():
            return True
        # Starship A3/A4: swarm tournament before stall remediation / phoenix.
        if bool(getattr(self.cur_cfg, "starship_stall_after_swarm_only", True)):
            if self._ensure_swarm_first() or bool(self.swarm_state.active):
                return True
        hard_stop = bool(getattr(self, "_hard_stop_terminal_armed", False))
        # Raptor v4: after hard-stop, at most one remediation cycle — then finalize.
        if hard_stop and int(self.remediation_state.remediation_cycle) >= 1:
            if self.bus.remediation_is_exhausted(self.stage) or not self.remediation_state.active:
                logger.warning(
                    "birth.terminal.finalized after_hard_stop_remediation cycle=%s step=%s",
                    self.remediation_state.remediation_cycle,
                    self.remediation_state.remediation_step,
                )
                return False
        if not self.bus.remediation_should_run(self.stage, plateau_exhausted=True):
            return False
        if self.bus.remediation_can_start(self.stage):
            if hard_stop and int(self.remediation_state.remediation_cycle) >= 1:
                logger.warning(
                    "birth.terminal.finalized block_extra_remediation_cycle cycle=%s",
                    self.remediation_state.remediation_cycle,
                )
                return False
            self.bus.remediation_begin_cycle(
                self.stage,
                stage_trades=self.stage_trades,
                stage_wins=self.stage_wins,
            )
            try:
                from lumina_core.notifications.milestone_events import (
                    stall_remediation_cycle_event,
                )

                self.host._notify_milestone(
                    stall_remediation_cycle_event(
                        cycle=self.remediation_state.remediation_cycle,
                        max_cycles=int(self.cur_cfg.stall_remediation_max_cycles),
                    )
                )
            except Exception as exc:
                logger.debug("birth.milestone_remediation_cycle_failed: %s", exc)
            self.plateau_state.active = False
            self.plateau_state.evolution_step = 0
            self.plateau_state.forced_recoveries_count = 0
        if self.bus.remediation_is_exhausted(self.stage):
            if hard_stop:
                logger.warning(
                    "birth.terminal.finalized remediation_exhausted_after_hard_stop cycle=%s",
                    self.remediation_state.remediation_cycle,
                )
                return False
            no_lift = should_brake_recovery_no_lift(
                self.plateau_state
            ) or should_block_phoenix_no_lift(self.plateau_state)
            if no_lift:
                logger.warning(
                    "birth.plateau.no_lift_brake blocking cycle/phoenix reset "
                    "cycles=%s best=%.2f%% cycle_start=%.2f%%",
                    self.plateau_state.full_recovery_cycles,
                    float(self.plateau_state.best_winrate) * 100.0,
                    float(self.plateau_state.best_winrate_at_cycle_start) * 100.0,
                )
                return False
            if self._trade_budget_remaining() > 0 and self.bus.remediation_can_start(self.stage):
                reset_plateau_for_new_cycle(
                    self.plateau_state,
                    stage_trades=self.stage_trades,
                    stage_wins=self.stage_wins,
                )
                self.remediation_state.active = False
                self.remediation_state.remediation_step = 0
                self.remediation_state.remediation_rollouts_this_step = 0
                fk = str(pending.get("failure_key") or "stage_metrics")
                return self._try_plateau_evolution(failure_key=fk)
            if self._trade_budget_remaining() > 0 and should_phoenix_reset(
                self.plateau_state,
                cfg=self.cur_cfg,
                winrate=float(self.stage_wins) / float(max(1, self.stage_trades)),
            ):
                self._apply_phoenix_reset()
                reset_plateau_for_new_cycle(
                    self.plateau_state,
                    stage_trades=self.stage_trades,
                    stage_wins=self.stage_wins,
                )
                self.remediation_state.active = False
                fk = str(pending.get("failure_key") or "stage_metrics")
                return self._try_plateau_evolution(failure_key=fk)
            if self.cur_cfg.autonomous_recovery_enabled and self._apply_phoenix_in_loop(
                stall_reason=TERMINAL_STALL_REASON
            ):
                return True
            return False
        action_raw = self.bus.remediation_begin_step(
            self.stage,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
        )
        action = StallRemediationAction(action_raw) if action_raw else None
        detail = self._apply_stall_remediation_action(action)
        self.bus.remediation_record_outcome(
            self.stage,
            action=action.value if action else None,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            detail=detail,
        )
        self.attempt = 0
        self.host._persist_checkpoint(
            training_mode=self.training_mode,
            curriculum_stage=self.stage.value,
            policy_path=str(self.host.final_policy_path),
            phase="stall_remediation",
            stage_metrics=self._stage_metrics_payload(),
        )
        self._write_progress(
            phase="stall_remediation",
            message=(
                f"Stall remediation step {self.remediation_state.remediation_step}/"
                f"{self.cur_cfg.stall_remediation_max_steps}: {detail}"
            ),
        )
        logger.info(
            "birth.stall_remediation.applied step=%s action=%s",
            self.remediation_state.remediation_step,
            action.value if action else "none",
        )
        return True

    def _maybe_advance_stall_remediation_in_loop(self) -> bool:
        """Advance remediation between rollouts; True if human gate finalize needed."""
        if not self.remediation_state.active:
            return False
        from lumina_core.birth.birth_control_plane import should_skip_plateau_ladder_theater

        if should_skip_plateau_ladder_theater(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
        ):
            # Seal: freeze/accept kills mid-cycle remediation theater too.
            try:
                self.remediation_state.active = False
            except Exception as exc:
                logger.debug("birth.stall_remediation.stop_after_freeze_failed: %s", exc)
            logger.info(
                "birth.stall_remediation.advance_skipped_after_swarm_freeze reject=%s accept=%s",
                bool(getattr(self, "swarm_rejected_no_lift", False)),
                bool(getattr(self, "swarm_champion_accepted", False)),
            )
            return False
        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        if not self.bus.remediation_should_advance(self.stage, current_winrate=current_winrate):
            return False
        if self.remediation_state.remediation_step >= int(self.cur_cfg.stall_remediation_max_steps):
            if self._apply_phoenix_in_loop(stall_reason=HUMAN_GATE_REASON):
                return False
            return not self.cur_cfg.autonomous_recovery_enabled
        action_raw = self.bus.remediation_begin_step(
            self.stage,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
        )
        action = StallRemediationAction(action_raw) if action_raw else None
        detail = self._apply_stall_remediation_action(action)
        self.bus.remediation_record_outcome(
            self.stage,
            action=action.value if action else None,
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            detail=detail,
        )
        self.attempt = 0
        self._write_progress(
            phase="stall_remediation",
            message=f"Stall remediation advanced: {detail}",
        )
        try:
            from lumina_core.notifications.milestone_events import (
                stall_remediation_step_event,
            )

            self.host._notify_milestone(
                stall_remediation_step_event(
                    cycle=self.remediation_state.remediation_cycle,
                    step=self.remediation_state.remediation_step,
                    max_steps=int(self.cur_cfg.stall_remediation_max_steps),
                    action=action.value if action else "",
                    detail=detail,
                    winrate=current_winrate,
                )
            )
        except Exception as exc:
            logger.debug("birth.milestone_remediation_step_failed: %s", exc)
        return self.remediation_state.remediation_step >= int(self.cur_cfg.stall_remediation_max_steps)
