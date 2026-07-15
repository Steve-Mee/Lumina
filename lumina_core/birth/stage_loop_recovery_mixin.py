"""StageLoopRecoveryMixin — StageLoopSession mixin."""

from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.curriculum import (
    filter_ticks_for_stage,
)
from lumina_core.birth.organism_autonomy import RecoveryDispatch
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    adaptation_stuck_escape_allowed,
    can_force_never_stop_recovery,
    record_forced_recovery,
    remediation_is_exhausted,
    reset_plateau_for_new_cycle,
    should_block_plateau_recovery,
    should_phoenix_reset,
)
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.remediation import filter_train_ticks_for_holdout_profile
from lumina_core.birth.stall_remediation import (
    HUMAN_GATE_REASON,
    StallRemediationAction,
    curate_buffer_bottom_half,
)
from lumina_core.birth.phoenix_loop import PHOENIX_CYCLE_REASON
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")

class StageLoopRecoveryMixin(StageLoopMixinBase):
    """See StageLoopSession for attributes."""

    def _trade_budget_remaining(self) -> int:
        return max(0, int(self.effective_trade_budget_cap) - int(self.host.cumulative_trades))

    def _remediation_exhausted_now(self) -> bool:
        return remediation_is_exhausted(
            remediation_active=self.remediation_state.active,
            remediation_step=self.remediation_state.remediation_step,
            remediation_cycle=self.remediation_state.remediation_cycle,
            cfg=self.cur_cfg,
        )

    def _wall_eval_context(self, 
        *,
        elapsed_stage_sec: float,
        failure_key: str,
        force: bool = False,
    ) -> dict[str, Any]:
        return {
            "stage_trades": self.stage_trades,
            "stage_wins": self.stage_wins,
            "required": self.required,
            "hold_ratio": float(self.stage_hold_signals) / float(max(1, self.stage_total_signals)),
            "constitution_violations": self.host._constitution_guard.violations,
            "range_flat_ratio": float(self.stage_range_flat_bars)
            / float(max(1, self.stage_range_total_signals)),
            "range_round_trips": self.stage_range_round_trips,
            "range_total_signals": self.stage_range_total_signals,
            "elapsed_stage_sec": elapsed_stage_sec,
            "winrate_stagnation_count": self.winrate_stagnation_count,
            "hold_stagnation_count": self.hold_stagnation_count,
            "wall_budget_exhausted": self.wall_budget_exhausted,
            "allow_provisional": self.allow_provisional,
            "failure_key": failure_key,
            "force": force,
            "low_velocity_attempts": self.low_velocity_attempts,
            "last_adaptation_stage_trades": self.last_adaptation_stage_trades,
        }

    def _evaluate_wall_trigger(self, 
        *,
        elapsed_stage_sec: float,
        failure_key: str,
        force: bool = False,
    ) -> dict[str, Any] | None:
        return self.bus.wall_evaluate_trigger(
            self.stage,
            **self._wall_eval_context(
                elapsed_stage_sec=elapsed_stage_sec,
                failure_key=failure_key,
                force=force,
            ),
        )

    def _would_certified_stage_stall(self, 
        *,
        elapsed_stage_sec: float,
        failure_key: str,
        force: bool = False,
    ) -> dict[str, Any] | None:
        trigger = self._evaluate_wall_trigger(
            elapsed_stage_sec=elapsed_stage_sec,
            failure_key=failure_key,
            force=force,
        )
        if trigger is None or not trigger.get("triggered"):
            return None
        pending = trigger.get("pending")
        return dict(pending) if isinstance(pending, dict) else None

    def _finalize_certified_stage_stall(self, 
        pending: dict[str, Any],
        *,
        human_gate: bool = False,
    ) -> dict[str, Any]:
        failure_key = str(pending["failure_key"])
        blocker_metric = pending["blocker_metric"]
        blocker_value = pending["blocker_value"]
        blocker_reason = pending.get("blocker_reason")
        logger.info(
            "birth.terminal_stall reason=%s cumulative_trades=%s cap=%s "
            "adaptation_tier=%s retries=%s data_exhausted=%s buffer=%s human_gate=%s",
            blocker_reason or failure_key,
            self.host.cumulative_trades,
            self.effective_trade_budget_cap,
            self.adaptation_tier,
            self.retries_this_stage,
            self.data_exhausted,
            len(self.host.buffer),
            human_gate,
        )
        stall_reason = str(
            pending.get("terminal_stall_reason")
            or pending.get("blocker_reason")
            or failure_key
            or blocker_metric
            or "stage_stalled"
        )
        stage_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        proxy_winrate = float(self.oos_proxy_history[-1]) if self.oos_proxy_history else None
        fitness_signal = max(stage_winrate, float(proxy_winrate or 0.0))
        recommended_recovery = str(
            pending.get("recommended_recovery_action")
            or self.organism_autonomy_state.last_recommended_action
            or ""
        )
        autonomy_decision = self.bus.autonomy_evaluate_terminal_stall(self.stage, 
            cfg=self.cur_cfg,
            autonomy_state=self.organism_autonomy_state,
            pending=pending,
            curriculum_stage=self.stage.value,
            stage_trades=self.stage_trades,
            required=self.required,
            constitution_violations=self.host._constitution_guard.violations,
            fitness_signal=fitness_signal,
            recommended_recovery_action=recommended_recovery,
            remediation_cycles_exhausted=stall_reason in {HUMAN_GATE_REASON, PHOENIX_CYCLE_REASON},
            plateau_exhausted=stall_reason == TERMINAL_STALL_REASON,
        )
        provisional_graduation = (
            autonomy_decision.dispatch == RecoveryDispatch.PROVISIONAL_GRADUATE
            or (
                self.cur_cfg.graduation_mode == "evolution_deferred"
                and (human_gate or self.cur_cfg.autonomous_recovery_enabled)
                and self.host._constitution_guard.violations == 0
                and self.stage_trades >= self.required
                and fitness_signal >= float(self.cur_cfg.provisional_oos_floor)
                and self.cur_cfg.allow_provisional_pass
            )
        )
        if autonomy_decision.stall_reason:
            stall_reason = autonomy_decision.stall_reason
        if self.host._constitution_guard.violations == 0 and self.stage_trades >= max(1, self.required // 2):
            try:
                from lumina_core.birth.dna_handoff import register_partial_birth_dna

                register_partial_birth_dna(
                    self.host.workspace_root,
                    curriculum_stage=self.stage.value,
                    stage_trades=self.stage_trades,
                    stage_winrate=stage_winrate,
                    oos_proxy_winrate=proxy_winrate,
                    policy_path=str(self.host.final_policy_path),
                    stall_reason=stall_reason,
                )
            except Exception as exc:
                logger.warning("birth.dna_handoff.partial_failed: %s", exc)
        if self.cur_cfg.autonomous_recovery_enabled:
            needs_attention = autonomy_decision.needs_attention and not provisional_graduation
            retryable = autonomy_decision.retryable or provisional_graduation
        else:
            needs_attention = (
                (bool(human_gate) or stall_reason in {TERMINAL_STALL_REASON, HUMAN_GATE_REASON})
                and not provisional_graduation
            )
            retryable = not needs_attention or provisional_graduation
        autonomy_extra: dict[str, Any] = {}
        if autonomy_decision.autonomy_metrics:
            autonomy_extra.update(autonomy_decision.autonomy_metrics)
        if autonomy_decision.recommended_action:
            autonomy_extra["recommended_recovery_action"] = autonomy_decision.recommended_action
            autonomy_extra["autonomous_recovery_pending"] = (
                self.cur_cfg.autonomous_recovery_enabled
                and autonomy_decision.dispatch
                in {RecoveryDispatch.PHOENIX_RESUME, RecoveryDispatch.CONTINUE_LOOP}
            )
        if autonomy_decision.message:
            autonomy_extra["autonomy_message"] = autonomy_decision.message
        write_birth_progress(
            self.host.workspace_root,
            stage="stage_stalled",
            phase="stage_stalled",
            message=(
                f"Stage {self.stage.value} stalled: "
                f"{blocker_reason or blocker_metric or failure_key}"
            ),
            progress_pct=self.stage_progress_pct,
            cumulative_trades=self.host.cumulative_trades,
            target_trades=self.effective_trade_budget_cap,
            birth_start_time=self.host.birth_start_time,
            curriculum_stage=self.stage.value,
            stages_passed=list(self.host._stages_passed),
            stage_blocker_metric=blocker_metric,
            stage_blocker_value=blocker_value,
            pass_reason=blocker_reason,
            retryable=retryable,
            needs_attention=needs_attention,
            provisional_graduation=provisional_graduation,
            graduation_tier="provisional" if provisional_graduation else "strict",
            oos_proxy_winrate=proxy_winrate,
            **self.host._budget_progress_fields(terminal_stall_reason=stall_reason),
            **self.host._constitution_progress_fields(),
            **autonomy_extra,
        )
        policy_hint = str(self.host.final_policy_path)
        if self.host.final_policy_path.is_file():
            policy_hint = str(self.host.final_policy_path)
        checkpoint_phase = "stage_stalled"
        if autonomy_decision.dispatch == RecoveryDispatch.PHOENIX_RESUME:
            checkpoint_phase = "phoenix_cycle"
        self.host._persist_checkpoint(
            training_mode=self.training_mode,
            curriculum_stage=self.stage.value,
            policy_path=policy_hint,
            phase=checkpoint_phase,
            stage_metrics=self._stage_metrics_payload(),
        )
        if autonomy_decision.checkpoint_patch and self.cur_cfg.autonomous_recovery_enabled:
            try:
                from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload

                ckpt = read_checkpoint_payload(self.host.workspace_root) or {}
                patch = autonomy_decision.checkpoint_patch
                ckpt_metrics = dict(ckpt.get("stage_metrics") or {})
                ckpt_metrics.update(dict(patch.get("stage_metrics") or {}))
                ckpt.update({k: v for k, v in patch.items() if k != "stage_metrics"})
                ckpt["stage_metrics"] = ckpt_metrics
                write_checkpoint_payload(self.host.workspace_root, ckpt)
            except Exception as exc:
                logger.warning("birth.autonomy.checkpoint_patch_failed: %s", exc)
        if provisional_graduation:
            logger.info(
                "birth.provisional_graduation stage=%s fitness=%.2f%% proxy=%s",
                self.stage.value,
                fitness_signal * 100.0,
                proxy_winrate,
            )
        if needs_attention:
            try:
                from lumina_core.notifications.attention_events import birth_stage_stalled_event
                from lumina_core.notifications.attention_notifier import notify_attention

                winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
                notify_attention(
                    birth_stage_stalled_event(
                        curriculum_stage=self.stage.value,
                        stall_reason=stall_reason,
                        blocker_detail=str(blocker_reason or blocker_metric or failure_key),
                        stage_trades=self.stage_trades,
                        winrate=winrate,
                        retryable=retryable,
                        phase2_active=self.remediation_state.active,
                    ),
                    workspace_root=self.host.workspace_root,
                )
            except Exception as exc:
                logger.warning("birth.attention_notify_failed: %s", exc)
        return {
            "status": "stage_stalled",
            "failure_reason": failure_key,
            "total_trades": self.host.cumulative_trades,
            "ppo_steps": self.host.ppo_steps,
            "training_mode": self.training_mode,
        }

    def _apply_phoenix_in_loop(self, *, stall_reason: str) -> bool:
        """Apply phoenix novelty inside rollout loop; True when loop should continue."""
        if not self.cur_cfg.autonomous_recovery_enabled or not self.cur_cfg.phoenix_loop_enabled:
            return False
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
            self.host.current_policy = self.host._create_birth_policy(allow_load_existing=False)
            if self.intra_state is not None:
                self.intra_state.hard_pct = 0.0
                self._rebuild_intra_pools(self.active_stage_ticks)
            self.strong_recovery_mode = True
            if detail:
                detail = f"{detail}; aggressive cycle {self.remediation_state.remediation_cycle}"
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
        if not self.bus.remediation_should_run(self.stage, plateau_exhausted=True):
            return False
        if self.bus.remediation_can_start(self.stage):
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

    def _resolve_terminal_stall(self, pending: dict[str, Any]) -> dict[str, Any] | None:
        """None => continue loop; dict => terminal stall result."""
        if self._try_stall_remediation_on_terminal(pending):
            return None
        stall_reason = str(
            pending.get("terminal_stall_reason") or pending.get("blocker_reason") or ""
        )
        if self.cur_cfg.autonomous_recovery_enabled:
            return self._finalize_certified_stage_stall(pending, human_gate=False)
        human_gate = stall_reason in {TERMINAL_STALL_REASON, HUMAN_GATE_REASON}
        return self._finalize_certified_stage_stall(pending, human_gate=human_gate)

    def _should_terminal_stall_in_adaptive(self) -> bool:
        """True when plateau recovery must stop (budget-gated never-stop)."""
        if self.plateau_state.active and should_block_plateau_recovery(
            self.plateau_state,
            cfg=self.cur_cfg,
            remediation_exhausted=self._remediation_exhausted_now(),
            trade_budget_remaining=self._trade_budget_remaining(),
            stage_trades=self.stage_trades,
            required=self.required,
        ):
            return True
        if self.plateau_state.active:
            return False
        if (
            self.data_exhausted
            and len(self.host.buffer) < 80
            and self.adaptation_tier >= self.cur_cfg.max_adaptation_tiers - 1
        ):
            return True
        return False

    def _maybe_extend_trade_budget(self) -> bool:
        if self.host.cumulative_trades < self.effective_trade_budget_cap:
            return False
        old_cap = self.effective_trade_budget_cap
        self.effective_trade_budget_cap = int(self.effective_trade_budget_cap * 1.25) + 1000
        logger.info(
            "birth.budget_extended old_cap=%s new_cap=%s cumulative_trades=%s tier=%s",
            old_cap,
            self.effective_trade_budget_cap,
            self.host.cumulative_trades,
            self.adaptation_tier,
        )
        return True

    def _sync_adaptation_from_bus(self) -> None:
        wa = self.bus.wall_adaptation_state
        self.retries_this_stage = int(wa.retries_this_stage)
        self.adaptation_tier = int(wa.adaptation_tier)
        self.escalation_level = int(wa.escalation_level)
        self.adaptation_history = list(wa.adaptation_history)
        self.last_adaptation_stage_trades = int(wa.last_adaptation_stage_trades)
        self.adaptation_stuck_escapes = int(wa.adaptation_stuck_escapes)

    def _apply_bus_adaptation_result(self, result: dict[str, Any]) -> bool:
        if not result.get("applied"):
            return False
        self._sync_adaptation_from_bus()
        decision = result.get("decision") if isinstance(result.get("decision"), dict) else {}
        chunk = decision.get("new_chunk_target")
        if chunk is not None:
            self.cur_cfg.rollout_chunk_trades = int(chunk)
        if result.get("mine"):
            self._mine_and_inject(aggressive=bool(result.get("mine_aggressive", False)))
        if result.get("expand_data"):
            self._maybe_expand_data()
        if result.get("spawn_plateau") and not self.plateau_state.active:
            self.bus.plateau_enter(self.stage, stage_trades=self.stage_trades, stage_wins=self.stage_wins)
            self.ppo_steps_at_plateau_evolution_step = int(self.host.ppo_steps)
        if result.get("spawn_phoenix_reset"):
            self._apply_phoenix_reset()
            reset_plateau_for_new_cycle(
                self.plateau_state,
                stage_trades=self.stage_trades,
                stage_wins=self.stage_wins,
            )
        self.attempt = 0
        self.winrate_stagnation_count = 0
        self.hold_stagnation_count = 0
        self.wall_budget_exhausted = False
        self.stage_started_at = time.time()
        self.host._persist_checkpoint(
            training_mode=self.training_mode,
            curriculum_stage=self.stage.value,
            policy_path=str(self.host.final_policy_path),
            phase="curriculum_learning",
            stage_metrics=self._stage_metrics_payload(),
        )
        logger.info(
            "birth.adaptation.applied reason=%s tier=%s new_chunk=%s escalation=%s",
            decision.get("reason", ""),
            self.adaptation_tier,
            self.cur_cfg.rollout_chunk_trades,
            self.escalation_level,
        )
        self._write_progress(
            phase="curriculum_learning",
            message=(
                f"Adaptive recovery tier {self.adaptation_tier + 1}/{self.cur_cfg.max_adaptation_tiers} "
                f"· retry {self.retries_this_stage}/{self.cur_cfg.max_stage_retries}: "
                f"{decision.get('log_message', '')}"
            ),
        )
        return True

    def _adaptation_recovery_context(self, 
        *,
        failure_key: str,
        trigger_type: str = "certified_stall",
        constitution_blocked: bool = False,
    ) -> dict[str, Any]:
        from lumina_core.birth.birth_bus_serde import serialize_learning_snapshot

        current_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
        snap_raw: dict[str, Any] | None = None
        learning_health = "flat"
        if self.cur_cfg.meta_controller_enabled:
            snap, _ = self._observe_snapshot()
            snap_raw = serialize_learning_snapshot(snap)
            learning_health = str(snap.learning_health.value)
        return {
            "trigger_type": trigger_type,
            "failure_key": failure_key,
            "stage_trades": self.stage_trades,
            "required": self.required,
            "current_winrate": current_winrate,
            "winrate_history": list(self.winrate_history),
            "original_rollout_chunk": self.original_rollout_chunk,
            "rollout_chunk_trades": self.cur_cfg.rollout_chunk_trades,
            "trade_budget_remaining": self._trade_budget_remaining(),
            "terminal_blocked": self._should_terminal_stall_in_adaptive(),
            "constitution_blocked": constitution_blocked,
            "learning_health": learning_health,
            "snapshot": snap_raw,
            "winrate": current_winrate,
            "escalation_level": self.escalation_level,
            "adaptation_tier": self.adaptation_tier,
            "retries_this_stage": self.retries_this_stage,
        }

    def _try_adaptive_stall_recovery(self, 
        *,
        failure_key: str,
        trigger_type: str = "certified_stall",
        constitution_blocked: bool = False,
    ) -> bool:
        if not self.cur_cfg.adaptation_enabled or self.cur_cfg.wall_behavior != "adaptive":
            return False
        self._maybe_extend_trade_budget()
        if self._should_terminal_stall_in_adaptive():
            return False
        result = self.bus.adaptation_try_recovery(
            self.stage,
            **self._adaptation_recovery_context(
                failure_key=failure_key,
                trigger_type=trigger_type,
                constitution_blocked=constitution_blocked,
            ),
        )
        return self._apply_bus_adaptation_result(result)

    def _force_never_stop_recovery(self, *, failure_key: str) -> bool:
        """Keep curriculum loop alive when recovery tiers remain (ADR-0017)."""
        if not self.cur_cfg.adaptation_enabled or self.cur_cfg.wall_behavior != "adaptive":
            return False
        if self._should_terminal_stall_in_adaptive():
            return False
        self._maybe_extend_trade_budget()
        if self.plateau_state.active and not can_force_never_stop_recovery(
            self.plateau_state, cfg=self.cur_cfg
        ):
            return self._try_plateau_evolution(failure_key=failure_key)
        if self.plateau_state.active:
            record_forced_recovery(self.plateau_state)
        logger.info(
            "birth.never_stop force_recovery failure=%s tier=%s retries=%s",
            failure_key,
            self.adaptation_tier,
            self.retries_this_stage,
        )
        result = self.bus.adaptation_never_stop(
            self.stage,
            failure_key=failure_key,
            rollout_chunk_trades=self.cur_cfg.rollout_chunk_trades,
            terminal_blocked=self._should_terminal_stall_in_adaptive(),
            current_winrate=float(self.stage_wins) / float(max(1, self.stage_trades)),
            stage_trades=self.stage_trades,
            original_rollout_chunk=self.original_rollout_chunk,
        )
        applied = self._apply_bus_adaptation_result(result)
        if applied and self.adaptation_tier >= 1:
            self._mine_and_inject()
        if applied and self.adaptation_tier >= 2 and self.cur_cfg.auto_expand_on_adaptation:
            self._maybe_expand_data()
        return applied

    def _try_adaptation_stuck_escape(self, *, failure_key: str) -> bool:
        if not adaptation_stuck_escape_allowed(
            escapes_used=self.adaptation_stuck_escapes,
            max_escapes=self.cur_cfg.max_adaptation_stuck_escapes,
            trade_budget_remaining=self._trade_budget_remaining(),
        ):
            return False
        logger.warning(
            "birth.adaptation.stuck_escape attempt=%s/%s trades=%s tier=%s failure=%s",
            self.adaptation_stuck_escapes + 1,
            self.cur_cfg.max_adaptation_stuck_escapes,
            self.stage_trades,
            self.adaptation_tier,
            failure_key,
        )
        self._maybe_extend_trade_budget()
        result = self.bus.adaptation_try_recovery(
            self.stage,
            **self._adaptation_recovery_context(
                failure_key=failure_key,
                trigger_type="adaptation_stuck",
            ),
        )
        return self._apply_bus_adaptation_result(result)

