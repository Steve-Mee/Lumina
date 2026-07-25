"""Post-rollout stagnation, PPO, milestones, plateau/remediation tail."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.plateau_escalator import (
    TERMINAL_STALL_REASON,
    update_plateau_quarantine_after_rollout,
)
from lumina_core.birth.stall_remediation import HUMAN_GATE_REASON
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_rollout_tail")


class StageLoopRolloutTailMixin(StageLoopMixinBase):
    """Stagnation counters, PPO update, milestones, plateau/remediation advance."""

    def _run_rollout_tail(
        self,
        *,
        rollout: Any,
        chunk_target: int,
        current_winrate: float,
        current_hold_ratio: float,
        metric_band: float,
    ) -> dict[str, Any] | None:
        if (
            self.stage == CurriculumStage.STAGE1_TREND
            and self.stage_trades >= self.required
            and (current_winrate < self.pass_metric_target or current_hold_ratio > 0.85)
        ):
            if abs(current_winrate - self.last_winrate) < 0.01 and abs(
                current_hold_ratio - self.last_hold_ratio
            ) < 0.01:
                self.winrate_stagnation_count += 1
            else:
                self.winrate_stagnation_count = 0
            self.last_winrate = current_winrate
            self.last_hold_ratio = current_hold_ratio
        elif (
            self.stage == CurriculumStage.STAGE2_RANGE
            and self.stage_trades >= self.required
            and (metric_band > 0.70 or metric_band < 0.30)
        ):
            if abs(metric_band - self.last_hold_ratio) < 0.01:
                self.hold_stagnation_count += 1
            else:
                self.hold_stagnation_count = 0
            self.last_hold_ratio = metric_band
        else:
            self.hold_stagnation_count = 0
            if self.stage != CurriculumStage.STAGE1_TREND:
                self.winrate_stagnation_count = 0

        for traj in rollout.trajectories:
            self.host.buffer.add(traj, priority=1.0 + min(10.0, abs(float(traj.get("reward", 0.0)))))

        if len(self.host.buffer) >= 256:
            stage_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
            self._write_progress(
                phase="ppo_training",
                message=(
                    f"PPO batch start · {self.stage_trades:,}/{self.required:,} trades · "
                    f"winrate {stage_winrate:.1%} · patronen {self.patterns_mined:,}"
                ),
                hold_ratio=float(self.stage_hold_signals) / float(max(1, self.stage_total_signals)),
            )
            self.host.current_policy = self.host.ppo_trainer.update_from_buffer(
                buffer=self.host.buffer,
                timesteps=self.ppo_steps_per_update,
                birth_phase=True,
            )
            self.host.ppo_steps += self.ppo_steps_per_update
            self.host._persist_checkpoint(
                training_mode=self.training_mode,
                curriculum_stage=self.stage.value,
                phase="ppo_training",
                stage_metrics=self._stage_metrics_payload(),
            )

        if rollout.stalled and self.stage_trades == 0 and self.patterns_mined == 0:
            self.escalation_level += 1
            if self.escalation_level >= self.cur_cfg.max_escalation_level:
                self._mine_and_inject()
                self._maybe_expand_data()
                self.escalation_level = 0
        elif rollout.trades == 0 or rollout.partial_complete:
            self.escalation_level = min(self.escalation_level + 1, self.cur_cfg.max_escalation_level - 1)
        elif rollout.trades < max(1, chunk_target // 4):
            self.escalation_level = min(self.escalation_level + 1, self.cur_cfg.max_escalation_level - 1)

        self.attempt += 1
        for pct in (50, 75, 90):
            if (
                pct not in self.budget_milestones_notified
                and self.effective_trade_budget_cap > 0
                and self.host.cumulative_trades * 100 // self.effective_trade_budget_cap >= pct
            ):
                self.budget_milestones_notified.add(pct)
                try:
                    from lumina_core.notifications.milestone_events import (
                        trade_budget_milestone_event,
                    )

                    self.host._notify_milestone(
                        trade_budget_milestone_event(
                            pct=pct,
                            cumulative_trades=self.host.cumulative_trades,
                            cap=self.effective_trade_budget_cap,
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_budget_failed: %s", exc)
        if self.winrate_history:
            prior_mean = sum(self.winrate_history) / float(len(self.winrate_history))
            if current_winrate >= prior_mean + 0.02:
                try:
                    from lumina_core.notifications.milestone_events import (
                        learning_breakthrough_event,
                    )

                    self.host._notify_milestone(
                        learning_breakthrough_event(
                            winrate=current_winrate,
                            prior_mean=prior_mean,
                            delta=current_winrate - prior_mean,
                        )
                    )
                except Exception as exc:
                    logger.debug("birth.milestone_breakthrough_failed: %s", exc)
        if self.plateau_state.active:
            self.bus.plateau_increment_rollout(self.stage)
            failure_key_rollout = {
                CurriculumStage.STAGE1_TREND: "stage1_winrate",
                CurriculumStage.STAGE2_RANGE: "stage2_metric",
                CurriculumStage.STAGE3_MIXED: "stage3_constitution",
            }.get(self.stage, "stage_metrics")
            if self._try_evolution_exhausted_remediation(failure_key=failure_key_rollout):
                self.attempt = 0
            else:
                self._maybe_advance_plateau_evolution_in_loop()
            # Fail-closed: after ladder work, terminal may now be due (compressed wall).
            terminal_pending = self._plateau_terminal_pending(failure_key=failure_key_rollout)
            if terminal_pending is not None:
                logger.warning(
                    "birth.terminal.hard_stop reason=%s step=%s trades=%s (post_rollout)",
                    terminal_pending.get("terminal_stall_reason") or TERMINAL_STALL_REASON,
                    self.plateau_state.evolution_step,
                    self.stage_trades,
                )
                self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                stall_result = self._resolve_terminal_stall(terminal_pending)
                if stall_result is not None:
                    return stall_result
        if self.remediation_state.active:
            self.bus.remediation_increment_rollout(self.stage)
            if self._maybe_advance_stall_remediation_in_loop():
                pending = self._plateau_terminal_pending(failure_key="stage1_winrate") or {
                    "failure_key": "stage1_winrate",
                    "blocker_metric": "trend_winrate",
                    "blocker_value": float(self.stage_wins) / float(max(1, self.stage_trades)),
                    "blocker_reason": HUMAN_GATE_REASON,
                    "terminal_stall_reason": HUMAN_GATE_REASON,
                }
                human_gate = not self.cur_cfg.autonomous_recovery_enabled
                stall_result = self._finalize_certified_stage_stall(
                    pending,
                    human_gate=human_gate,
                )
                return stall_result
        update_plateau_quarantine_after_rollout(
            self.plateau_quarantine,
            stage_trades=self.stage_trades,
        )
        self._maybe_detect_plateau(stage_trades=self.stage_trades, stage_wins=self.stage_wins)
        self._maybe_save_best_policy(stage_trades=self.stage_trades, stage_wins=self.stage_wins)
        self._maybe_periodic_checkpoint("curriculum_learning")
        self._write_progress(
            phase="curriculum_learning",
            message=(
                f"Curriculum {self.stage.value}: {self.stage_trades:,} / {self.required:,} trades · "
                f"poging {self.attempt} · patronen {self.patterns_mined:,}{self.meta_message_suffix}"
            ),
            hold_ratio=current_hold_ratio,
        )
        self.meta_message_suffix = ""
        return None
