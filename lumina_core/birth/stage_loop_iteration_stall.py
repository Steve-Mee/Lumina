"""Stall / wall / plateau branch for stage-loop iteration (moved intact)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.plateau_escalator import (
    evolution_ladder_exhausted,
    should_trigger_plateau_evolution_step,
)
from lumina_core.birth.stage_loop_iteration_helpers import LoopAction, stage_winrate
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_iteration.stall")


class StageLoopIterationStallMixin:
    """Handles wall-trigger stall_pending branch; returns (action, optional payload)."""

    def _iteration_handle_stall_pending(
        self,
        *,
        stall_pending: dict[str, Any],
        failure_key: str,
        trigger_type: str,
        constitution_blocked: bool,
        trades_beyond_hard_stop: bool,
    ) -> tuple[LoopAction, dict[str, Any] | None]:
        beyond_gate = bool(trades_beyond_hard_stop and self.stage_trades >= self.required)
        if beyond_gate and not self.plateau_state.active:
            self._maybe_detect_plateau(stage_trades=self.stage_trades, stage_wins=self.stage_wins)
        adaptation_stuck = trigger_type == "adaptation_stuck"
        force_train_lap = False
        if adaptation_stuck:
            logger.warning(
                "birth.adaptation.loop_blocked trades=%s tier=%s failure=%s "
                "rollouts_since_adapt=%s",
                self.stage_trades,
                self.adaptation_tier,
                failure_key,
                int(getattr(self, "rollouts_since_last_adaptation", 0) or 0),
            )
            if self._try_adaptation_stuck_escape(failure_key=failure_key):
                return "continue", None
            if self.plateau_state.active and self._try_plateau_evolution(failure_key=failure_key):
                self.rollouts_since_last_adaptation = 0
                self.last_adaptation_stage_trades = -1
                return "continue", None
            if self._force_never_stop_recovery(failure_key=failure_key):
                self.rollouts_since_last_adaptation = 0
                self.last_adaptation_stage_trades = -1
                return "continue", None
            if not getattr(self, "_adaptation_stuck_train_grace_used", False):
                self._adaptation_stuck_train_grace_used = True
                self.rollouts_since_last_adaptation = 0
                self.last_adaptation_stage_trades = -1
                logger.warning(
                    "birth.adaptation.stuck_train_grace trades=%s — continue rollouts",
                    self.stage_trades,
                )
                return "continue", None
            force_train_lap = True
        elif beyond_gate:
            current_wr = stage_winrate(self.stage_wins, self.stage_trades)
            if self.plateau_state.active and should_trigger_plateau_evolution_step(
                self.plateau_state,
                cfg=self.cur_cfg,
                current_winrate=current_wr,
                allow_start=False,
                pass_target=self._plateau_pass_target(),
                stage_trades=self.stage_trades,
                required=self.required,
            ) and self._try_plateau_evolution(failure_key=failure_key):
                return "continue", None
            if self.plateau_state.active and evolution_ladder_exhausted(
                self.plateau_state,
                stage=self.stage,
                max_steps=self._evolution_max_steps(),
            ):
                if self._try_evolution_exhausted_remediation(failure_key=failure_key):
                    return "continue", None
                plateau_terminal = self._plateau_terminal_pending(failure_key=failure_key)
                if plateau_terminal is not None:
                    self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                    stall_result = self._resolve_terminal_stall(plateau_terminal)
                    if stall_result is None:
                        return "continue", None
                    return "return", stall_result
            evo_rollouts = int(getattr(self.plateau_state, "evolution_rollouts_this_step", 0) or 0)
            evo_need = int(getattr(self.cur_cfg, "plateau_evolution_rollouts_per_step", 12) or 12)
            logger.warning(
                "birth.beyond_gate.force_train_lap trades=%s wr=%.2f%% "
                "plateau=%s evo_step=%s rollouts_this_step=%s/%s "
                "rollouts_since_adapt=%s — skip recovery spam",
                self.stage_trades,
                current_wr * 100.0,
                bool(self.plateau_state.active),
                int(getattr(self.plateau_state, "evolution_step", 0) or 0),
                evo_rollouts,
                evo_need,
                int(getattr(self, "rollouts_since_last_adaptation", 0) or 0),
            )
            force_train_lap = True
        elif self._try_adaptive_stall_recovery(
            failure_key=failure_key,
            trigger_type=trigger_type,
            constitution_blocked=constitution_blocked,
        ):
            return "continue", None
        if not force_train_lap:
            current_wr = stage_winrate(self.stage_wins, self.stage_trades)
            if self.plateau_state.active and should_trigger_plateau_evolution_step(
                self.plateau_state,
                cfg=self.cur_cfg,
                current_winrate=current_wr,
                allow_start=False,
                pass_target=self._plateau_pass_target(),
                stage_trades=self.stage_trades,
                required=self.required,
            ) and self._try_plateau_evolution(failure_key=failure_key):
                return "continue", None
            if not adaptation_stuck and self._force_never_stop_recovery(failure_key=failure_key):
                return "continue", None
            if self.plateau_state.active and self._try_plateau_evolution(failure_key=failure_key):
                return "continue", None
            if self.plateau_state.active and evolution_ladder_exhausted(
                self.plateau_state,
                stage=self.stage,
                max_steps=self._evolution_max_steps(),
            ):
                if self._try_evolution_exhausted_remediation(failure_key=failure_key):
                    return "continue", None
            plateau_terminal = self._plateau_terminal_pending(failure_key=failure_key)
            if plateau_terminal is not None:
                self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                stall_result = self._resolve_terminal_stall(plateau_terminal)
                if stall_result is None:
                    return "continue", None
                return "return", stall_result
            self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
            stall_result = self._resolve_terminal_stall(stall_pending)
            if stall_result is None:
                return "continue", None
            return "return", stall_result
        # force_train_lap: fall through to rollout body
        return "fallthrough", None
