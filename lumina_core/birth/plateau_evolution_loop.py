"""Plateau evolution finalize + best-policy helpers (M5 slim loop module).

Advance/detect live in ``plateau_evolution_advance`` / ``plateau_evolution_detect``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.plateau_escalator import (
    EvolutionAction,
    maybe_update_best_winrate,
    record_evolution_outcome,
    revert_evolution_step_on_noop,
)
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_mixin")


class PlateauEvolutionLoopMixin(StageLoopMixinBase):
    """Finalize steps, persist best policy, effective rollout caps."""

    def _finalize_plateau_evolution_step(
        self,
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

    def _maybe_save_best_policy(self, *, stage_trades: int, stage_wins: int) -> None:
        del stage_trades, stage_wins
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
        return (
            self.host.workspace_root
            / "lumina_agents"
            / "ppo"
            / f"birth_best_{self.stage.value}.zip"
        )

    def _meta_self_eval_phase_str(self) -> str:
        if self.cur_cfg.meta_controller_enabled and self.cur_cfg.meta_self_eval_enabled:
            return str(self.bus.meta_self_eval_state(self.stage).get("phase", ""))
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
        if self.plateau_state.evolution_step > 0 or self.plateau_state.active:
            return min(self.max_rollouts, self.cur_cfg.plateau_evolution_rollouts_per_step)
        return self.max_rollouts


__all__ = ["PlateauEvolutionLoopMixin"]
