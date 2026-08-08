"""Session prepare: plateau/swarm/quarantine resume (M5)."""
from __future__ import annotations


from lumina_core.birth.checkpoint import apply_plateau_quarantine_on_checkpoint_resume
from lumina_core.birth.curriculum import stage1_winrate_pass_threshold
from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    enter_plateau,
    evolution_ladder_exhausted,
    is_valid_best_policy_snapshot,
    reset_plateau_for_new_cycle,
    sanitize_phantom_evolution_steps,
    sanitize_plateau_best_snapshot,
    sanitize_stuck_plateau_evolution,
    should_block_phoenix_no_lift,
    should_brake_recovery_no_lift,
    should_trades_beyond_gate_hard_stop,
)
from lumina_core.birth.policy_swarm import PolicySwarmState
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session_runner")


class SessionPhasePreparePlateauMixin:
    def _prepare_restore_plateau_swarm(self) -> None:
        """Plateau sanitize, swarm resume, deep-stuck resume."""
        if self.plateau_state.active:
            sanitize_plateau_best_snapshot(
                self.plateau_state,
                cfg=self.cur_cfg,
                stage_trades=self.stage_trades,
                stage_wins=self.stage_wins,
            )
            stage_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
            sanitize_stuck_plateau_evolution(
                self.plateau_state,
                cfg=self.cur_cfg,
                current_winrate=stage_winrate,
                pass_target=stage1_winrate_pass_threshold(self.cur_cfg),
            )
            sanitize_phantom_evolution_steps(self.plateau_state)
        if self.metrics_match_stage and isinstance(self.stage_metrics, dict):
            for key in (
                "plateau_quarantine_active",
                "plateau_quarantine_rollouts_remaining",
                "plateau_quarantine_trades_remaining",
                "plateau_quarantine_trades_at_resume",
            ):
                if key in self.stage_metrics:
                    self.plateau_quarantine[key] = self.stage_metrics[key]
            # Restore best-policy snapshot before resume recovery decisions.
            for bp_key, attr in (
                ("plateau_best_winrate", "best_winrate"),
                ("best_winrate", "best_winrate"),
                ("plateau_best_winrate_at_trade", "best_winrate_at_trade"),
                ("best_winrate_at_trade", "best_winrate_at_trade"),
                ("plateau_best_policy_path", "best_policy_path"),
                ("best_policy_path", "best_policy_path"),
            ):
                if bp_key in self.stage_metrics and self.stage_metrics.get(bp_key):
                    raw = self.stage_metrics[bp_key]
                    if attr == "best_policy_path":
                        self.plateau_state.best_policy_path = str(raw or "")
                    elif attr == "best_winrate":
                        self.plateau_state.best_winrate = float(raw or 0.0)
                    elif attr == "best_winrate_at_trade":
                        self.plateau_state.best_winrate_at_trade = int(raw or 0)
            # Starship resume: restore champion freeze + swarm reject / re-swarm cap.
            if self.stage_metrics.get("best_edgescore") is not None:
                self.best_edgescore = float(self.stage_metrics.get("best_edgescore", 0.0) or 0.0)
            if self.stage_metrics.get("best_edgescore_at_trade") is not None:
                self.best_edgescore_at_trade = int(
                    self.stage_metrics.get("best_edgescore_at_trade", 0) or 0
                )
            if self.stage_metrics.get("best_edgescore_policy_path"):
                self.best_edgescore_policy_path = str(
                    self.stage_metrics.get("best_edgescore_policy_path") or ""
                )
            # Fail-closed: drop early/noise EdgeScore champions before freeze can arm.
            try:
                from lumina_core.birth.starship_birth import sanitize_edgescore_champion

                plateau_wr = float(
                    self.stage_metrics.get("plateau_best_winrate")
                    or self.stage_metrics.get("best_winrate")
                    or getattr(self.plateau_state, "best_winrate", 0.0)
                    or 0.0
                )
                best, at_trade, cleared = sanitize_edgescore_champion(
                    best_edgescore=float(getattr(self, "best_edgescore", 0.0) or 0.0),
                    best_edgescore_at_trade=int(
                        getattr(self, "best_edgescore_at_trade", 0) or 0
                    ),
                    best_winrate=plateau_wr,
                    required=int(self.required),
                    cfg=self.cur_cfg,
                )
                self.best_edgescore = best
                self.best_edgescore_at_trade = at_trade
                if cleared:
                    self.best_edgescore_policy_path = ""
            except Exception as exc:
                logger.debug("birth.starship.champion_sanitize_resume_failed: %s", exc)
            self.swarm_retearnament_used = bool(
                self.stage_metrics.get("swarm_retearnament_used", False)
            )
            self.swarm_rejected_no_lift = bool(
                self.stage_metrics.get("swarm_rejected_no_lift", False)
            )
            lift_ok = self.stage_metrics.get("swarm_tournament_lift_ok")
            if lift_ok is None:
                lift_ok = self.stage_metrics.get("swarm_edgescore_lift_ok", False)
            self.swarm_tournament_lift_ok = bool(lift_ok)
            self.swarm_edgescore_lift_ok = self.swarm_tournament_lift_ok
            at_start = self.stage_metrics.get("swarm_tournament_at_start")
            if at_start is None:
                at_start = self.stage_metrics.get("swarm_edgescore_at_start")
            if at_start is not None:
                self.swarm_tournament_at_start = float(at_start or -1.0)
                self.swarm_edgescore_at_start = self.swarm_tournament_at_start
            self.swarm_champion_accepted = bool(
                self.stage_metrics.get("swarm_champion_accepted", False)
            )
            try:
                self.swarm_state = PolicySwarmState.from_metrics(self.stage_metrics)
                if self.swarm_rejected_no_lift:
                    self.swarm_state.rejected_no_lift = True
                if self.swarm_champion_accepted:
                    self.swarm_state.champion_accepted = True
                # Fail-closed: active swarm without variants or in-memory windows.
                from lumina_core.birth.birth_control_plane import (
                    fail_closed_missing_frozen_windows,
                    require_frozen_windows_or_fail,
                )

                incomplete = self.swarm_state.active and (
                    not self.swarm_state.variants
                    or not require_frozen_windows_or_fail(self.swarm_state)
                )
                if incomplete:
                    if not self.swarm_state.variants:
                        self.swarm_state.active = False
                        self.swarm_rejected_no_lift = True
                        self.swarm_state.rejected_no_lift = True
                        self.swarm_fail_reason_code = "swarm_incomplete_restore"
                    else:
                        fail_closed_missing_frozen_windows(self.swarm_state, host=self)
                        self.swarm_rejected_no_lift = True
                        self.swarm_fail_reason_code = "swarm_frozen_windows_missing"
                    logger.warning(
                        "birth.swarm.resume_fail_closed reason=%s variants=%s windows=%s",
                        getattr(self, "swarm_fail_reason_code", ""),
                        len(self.swarm_state.variants or []),
                        len(self.swarm_state.frozen_tick_windows or []),
                    )
            except Exception as exc:
                logger.warning("birth.swarm.resume_restore_failed: %s", exc)
                swarm = getattr(self, "swarm_state", None)
                if swarm is not None and bool(getattr(swarm, "active", False)):
                    swarm.active = False
                    swarm.rejected_no_lift = True
                self.swarm_rejected_no_lift = True
                self.swarm_fail_reason_code = "swarm_incomplete_restore"
                logger.warning(
                    "birth.swarm.resume_fail_closed reason=swarm_incomplete_restore "
                    "(exception path)"
                )
            self.plateau_quarantine.update(
                apply_plateau_quarantine_on_checkpoint_resume(
                    cfg=self.cur_cfg,
                    stage_trades=self.stage_trades,
                    required=self.required,
                )
            )
            deep_stuck = should_trades_beyond_gate_hard_stop(
                self.stage_trades, self.required, self.cur_cfg
            )
            skipped = str(
                self.plateau_quarantine.get("plateau_quarantine_skipped_reason") or ""
            )
            if deep_stuck or skipped == "beyond_hard_stop":
                # Raptor v2: no quiet grace period when already past hard stop.
                # Enter plateau and jump straight to policy_rollback when snapshot exists.
                self.low_velocity_attempts = max(
                    self.low_velocity_attempts,
                    int(self.cur_cfg.velocity_stall_attempt_threshold),
                )
                no_lift_brake = should_brake_recovery_no_lift(
                    self.plateau_state
                ) or should_block_phoenix_no_lift(self.plateau_state)
                if no_lift_brake:
                    logger.warning(
                        "birth.plateau.deep_resume_braked_no_lift cycles=%s "
                        "best=%.2f%% cycle_start=%.2f%% trades=%s",
                        self.plateau_state.full_recovery_cycles,
                        float(self.plateau_state.best_winrate) * 100.0,
                        float(self.plateau_state.best_winrate_at_cycle_start) * 100.0,
                        self.stage_trades,
                    )
                    self._pending_deep_resume_harvest = False
                else:
                    # Ladder wrap must account cycles — never silent step-1 restart.
                    if (
                        evolution_ladder_exhausted(self.plateau_state)
                        and self.plateau_state.evolution_history
                    ):
                        reset_plateau_for_new_cycle(
                            self.plateau_state,
                            stage_trades=self.stage_trades,
                            stage_wins=self.stage_wins,
                        )
                    else:
                        enter_plateau(
                            self.plateau_state,
                            stage_trades=self.stage_trades,
                            stage_wins=self.stage_wins,
                        )
                    if is_valid_best_policy_snapshot(self.plateau_state, cfg=self.cur_cfg):
                        # EVOLUTION_STEP_ACTIONS[1] == POLICY_ROLLBACK (1-based step 2)
                        self.plateau_state.evolution_step = 1
                        self.plateau_state.evolution_rollouts_this_step = 0
                        detail, applied = self._apply_plateau_evolution_action(
                            EvolutionAction.POLICY_ROLLBACK
                        )
                        logger.warning(
                            "birth.plateau.deep_resume_rollback applied=%s detail=%s "
                            "trades=%s best_wr=%.2f%% cycles=%s",
                            applied,
                            detail,
                            self.stage_trades,
                            float(self.plateau_state.best_winrate) * 100.0,
                            self.plateau_state.full_recovery_cycles,
                        )
                        if applied:
                            self.plateau_state.evolution_step = 2
                            self.plateau_state.evolution_rollouts_this_step = 0
                    else:
                        self.plateau_state.evolution_step = 0
                        self.plateau_state.evolution_rollouts_this_step = 0
                        logger.warning(
                            "birth.plateau.deep_resume_enter trades=%s "
                            "(no valid best snapshot for rollback)",
                            self.stage_trades,
                        )
                    self._pending_deep_resume_harvest = True
            else:
                self.low_velocity_attempts = 0
                self.plateau_state.active = False
                self.plateau_state.evolution_step = 0
                self.plateau_state.evolution_rollouts_this_step = 0
                logger.warning(
                    "birth.plateau.quarantine resume trades=%s rollouts=%s min_trades=%s",
                    self.stage_trades,
                    self.plateau_quarantine.get("plateau_quarantine_rollouts_remaining"),
                    self.plateau_quarantine.get("plateau_quarantine_trades_remaining"),
                )

