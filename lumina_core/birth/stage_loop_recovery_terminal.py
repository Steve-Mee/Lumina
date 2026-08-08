"""Wall trigger + certified terminal stall finalization (stage-loop recovery)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.organism_autonomy import RecoveryDispatch
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    should_block_phoenix_no_lift,
    should_brake_recovery_no_lift,
)
from lumina_core.birth.progress import merge_birth_progress_extra, write_birth_progress
from lumina_core.birth.stall_remediation import HUMAN_GATE_REASON
from lumina_core.birth.phoenix_loop import PHOENIX_CYCLE_REASON
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_recovery_terminal")


class StageLoopRecoveryTerminalMixin(StageLoopMixinBase):
    """Wall evaluation and fail-closed terminal stall finalization."""

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
            "rollouts_since_last_adaptation": int(
                getattr(self, "rollouts_since_last_adaptation", 0) or 0
            ),
            "policy_entropy": self._resolve_policy_entropy(),
            "ppo_steps": int(getattr(self.host, "ppo_steps", 0) or 0),
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
        # Raptor v9: never KeyError on incomplete wall/plateau pendings.
        # Raptor v10: adaptation_stuck is an engineering signal — prefer skill blockers.
        pending = dict(pending or {})
        failure_key = str(pending.get("failure_key") or "stage_stalled")
        blocker_metric = pending.get("blocker_metric")
        blocker_value = pending.get("blocker_value")
        blocker_reason = pending.get("blocker_reason")
        engineering_stuck = (
            failure_key == "adaptation_stuck"
            or str(blocker_metric or "") == "adaptation_stuck"
            or str(blocker_reason or "") == "adaptation_loop_blocked"
        )
        need_skill_fill = (
            blocker_metric is None
            or blocker_value is None
            or engineering_stuck
        )
        if need_skill_fill:
            try:
                from lumina_core.birth.stage_scorecard import compute_stage_blocker

                hold_ratio = float(self.stage_hold_signals) / float(
                    max(1, self.stage_total_signals)
                )
                range_flat_ratio = float(self.stage_range_flat_bars) / float(
                    max(1, self.stage_range_total_signals)
                )
                bm, bv, br = compute_stage_blocker(
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
                if engineering_stuck and bm is not None:
                    pending["engineering_blocker"] = "adaptation_stuck"
                    blocker_metric = bm
                    blocker_value = bv if bv is not None else 0.0
                    blocker_reason = br or blocker_reason
                else:
                    if blocker_metric is None:
                        blocker_metric = bm or failure_key or "stage_stalled"
                    if blocker_value is None:
                        blocker_value = bv if bv is not None else 0.0
                    if not blocker_reason:
                        blocker_reason = br or failure_key
            except Exception:
                blocker_metric = blocker_metric or failure_key or "stage_stalled"
                blocker_value = 0.0 if blocker_value is None else blocker_value
                blocker_reason = blocker_reason or failure_key
        pending["failure_key"] = failure_key
        pending["blocker_metric"] = blocker_metric
        pending["blocker_value"] = blocker_value
        if blocker_reason:
            pending["blocker_reason"] = blocker_reason
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
        recovery_no_lift_brake = should_brake_recovery_no_lift(
            self.plateau_state
        ) or should_block_phoenix_no_lift(self.plateau_state)
        from lumina_core.birth.birth_control_plane import swarm_tournament_resolved

        swarm_resolved = swarm_tournament_resolved(
            swarm_state=self.swarm_state,
            host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
            host_committed=bool(
                str(getattr(self.swarm_state, "committed_variant_id", "") or "").strip()
            ),
        )
        try:
            live_edge = float(self._current_edgescore())
        except Exception:
            live_edge = float(getattr(self, "best_edgescore", 0.0) or 0.0)
        starship_ctx = {
            "edgescore": live_edge,
            "best_edgescore": float(getattr(self, "best_edgescore", 0.0) or 0.0),
            "swarm_rejected_no_lift": bool(
                getattr(self, "swarm_rejected_no_lift", False)
                or getattr(self.swarm_state, "rejected_no_lift", False)
            ),
            "swarm_champion_accepted": bool(
                getattr(self, "swarm_champion_accepted", False)
                or getattr(self.swarm_state, "champion_accepted", False)
            ),
        }
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
            recovery_no_lift_brake=recovery_no_lift_brake,
            swarm_tournament_resolved=swarm_resolved,
            starship_context=starship_ctx,
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
                in {
                    RecoveryDispatch.PHOENIX_RESUME,
                    RecoveryDispatch.CONTINUE_LOOP,
                    RecoveryDispatch.ACCEPT_CHAMPION_RESUME,
                }
            )
        if autonomy_decision.message:
            autonomy_extra["autonomy_message"] = autonomy_decision.message

        # Twin / autonomy accept_champion: clear freeze in-process and continue loop.
        if (
            autonomy_decision.dispatch == RecoveryDispatch.ACCEPT_CHAMPION_RESUME
            and self.cur_cfg.autonomous_recovery_enabled
        ):
            try:
                self.swarm_state.rejected_no_lift = False
                self.swarm_state.champion_accepted = True
                self.swarm_state.active = False
                self.swarm_rejected_no_lift = False
                self.swarm_champion_accepted = True
                # Restore champion policy for quality ladder.
                for path in (
                    str(getattr(self, "best_edgescore_policy_path", "") or "").strip(),
                    str(getattr(self.plateau_state, "best_policy_path", "") or "").strip(),
                    str(getattr(self.swarm_state, "pre_swarm_policy_path", "") or "").strip(),
                ):
                    if path and Path(path).is_file():
                        self.host.current_policy = self.host._create_birth_policy(
                            allow_load_existing=True,
                            policy_path=path,
                        )
                        break
                logger.info(
                    "birth.twin_accept_champion stage=%s conf=%s",
                    self.stage.value,
                    (autonomy_decision.autonomy_metrics or {}).get("twin_confidence"),
                )
                needs_attention = False
                retryable = True
                autonomy_extra["swarm_rejected_no_lift"] = False
                autonomy_extra["swarm_champion_accepted"] = True
                autonomy_extra["twin_accept_champion"] = True
                autonomy_extra["needs_attention"] = False
                # Persist clear freeze + continue curriculum (not stage_stalled terminal).
                write_birth_progress(
                    self.host.workspace_root,
                    stage="training_running",
                    phase="curriculum_learning",
                    message=(
                        autonomy_decision.message
                        or "Twin accept_champion — freeze cleared, quality ladder continues"
                    ),
                    progress_pct=self.stage_progress_pct,
                    cumulative_trades=self.host.cumulative_trades,
                    target_trades=self.effective_trade_budget_cap,
                    birth_start_time=self.host.birth_start_time,
                    **merge_birth_progress_extra(
                        self.host._budget_progress_fields(),
                        self.host._constitution_progress_fields(),
                        autonomy_extra,
                        {
                            "curriculum_stage": self.stage.value,
                            "stages_passed": list(self.host._stages_passed),
                            "swarm_rejected_no_lift": False,
                            "swarm_champion_accepted": True,
                            "needs_attention": False,
                            "retryable": True,
                        },
                    ),
                )
                self.host._persist_checkpoint(
                    training_mode=self.training_mode,
                    curriculum_stage=self.stage.value,
                    policy_path=str(self.host.final_policy_path),
                    phase="curriculum_learning",
                    stage_metrics=self._stage_metrics_payload(),
                )
                return None  # continue stage loop
            except Exception as exc:
                logger.warning("birth.twin_accept_champion_apply_failed: %s", exc)
        # Merge extras first — phoenix autonomy_metrics may include curriculum_stage
        # (PEP 448 dual-kwargs TypeError if unpacked alongside explicit kwargs).
        stall_extra = merge_birth_progress_extra(
            self.host._budget_progress_fields(terminal_stall_reason=stall_reason),
            self.host._constitution_progress_fields(),
            autonomy_extra,
            {
                "curriculum_stage": self.stage.value,
                "stages_passed": list(self.host._stages_passed),
                "stage_blocker_metric": blocker_metric,
                "stage_blocker_value": blocker_value,
                "pass_reason": blocker_reason,
                "retryable": retryable,
                "needs_attention": needs_attention,
                "provisional_graduation": provisional_graduation,
                "graduation_tier": "provisional" if provisional_graduation else "strict",
                "oos_proxy_winrate": proxy_winrate,
            },
        )
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
            **stall_extra,
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
