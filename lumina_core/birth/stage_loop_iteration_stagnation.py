"""Stagnation + max-rollouts branches for stage-loop iteration."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.curriculum import should_gen0_soft_pass
from lumina_core.birth.plateau_escalator import should_trigger_plateau_evolution_step
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.stage_loop_iteration_helpers import (
    LoopAction,
    force_failure_key_for_stage,
    history_unavailable_result,
    stage_winrate,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_iteration.stagnation")


class StageLoopIterationStagnationMixin:
    def _iteration_handle_stagnation(self) -> tuple[LoopAction, dict[str, Any] | None]:
        if self.stage_trades == self.last_stage_trades:
            self.stagnation_count += 1
        else:
            self.stagnation_count = 0
            self.last_stage_trades = self.stage_trades

        if self.stagnation_count < self.cur_cfg.stagnation_rollouts_before_expand:
            return "fallthrough", None

        self._mine_and_inject()
        if not self._maybe_expand_data():
            if self.allow_provisional and (
                self.stage_trades > 0 or self.patterns_mined > 0 or len(self.host.buffer) >= 256
            ):
                self.gen0_provisional = True
                return "continue", None
            if self.data_exhausted:
                write_birth_progress(
                    self.host.workspace_root,
                    stage="history_unavailable",
                    phase="data_expansion_exhausted",
                    message="Birth research: geen extra data/patronen beschikbaar.",
                    progress_pct=self.stage_progress_pct,
                    cumulative_trades=self.host.cumulative_trades,
                    target_trades=self.trade_budget_cap,
                    birth_start_time=self.host.birth_start_time,
                    curriculum_stage=self.stage.value,
                    retryable=True,
                )
                return (
                    "return",
                    history_unavailable_result(
                        total_trades=self.host.cumulative_trades,
                        ppo_steps=self.host.ppo_steps,
                    ),
                )
        self.stagnation_count = 0
        if len(self.host.buffer) >= 80:
            self.host.current_policy = self.host.ppo_trainer.update_from_buffer(
                buffer=self.host.buffer,
                timesteps=self.ppo_steps_per_update,
                birth_phase=True,
            )
            self.host.ppo_steps += self.ppo_steps_per_update
            self._capture_trainer_policy_entropy()
        return "fallthrough", None

    def _iteration_handle_max_rollouts(self) -> tuple[LoopAction, dict[str, Any] | None]:
        if self.attempt < self._effective_max_rollouts():
            return "fallthrough", None

        if self.allow_provisional and (
            should_gen0_soft_pass(
                stage_trades=self.stage_trades,
                buffer_size=len(self.host.buffer),
                attempt=self.attempt,
                cfg=self.cur_cfg,
            )
            or self.patterns_mined >= 100
        ):
            self.gen0_provisional = True
        elif self.allow_provisional and (self.stage_trades > 0 or self.patterns_mined > 0):
            self.gen0_provisional = True
        elif not self.allow_provisional and self.stage_trades >= self.required:
            force_failure_key = force_failure_key_for_stage(self.stage)
            stall_pending = self._would_certified_stage_stall(
                elapsed_stage_sec=time.time() - self.stage_started_at,
                failure_key=force_failure_key,
                force=True,
            )
            if stall_pending is not None:
                if self._try_adaptive_stall_recovery(failure_key=force_failure_key):
                    self.attempt = 0
                    return "continue", None
                force_wr = stage_winrate(self.stage_wins, self.stage_trades)
                if self.plateau_state.active and should_trigger_plateau_evolution_step(
                    self.plateau_state,
                    cfg=self.cur_cfg,
                    current_winrate=force_wr,
                    allow_start=False,
                    pass_target=self._plateau_pass_target(),
                ) and self._try_plateau_evolution(failure_key=force_failure_key):
                    self.attempt = 0
                    return "continue", None
                if self._force_never_stop_recovery(failure_key=force_failure_key):
                    self.attempt = 0
                    return "continue", None
                if self.plateau_state.active and self._try_plateau_evolution(
                    failure_key=force_failure_key
                ):
                    self.attempt = 0
                    return "continue", None
                plateau_terminal = self._plateau_terminal_pending(failure_key=force_failure_key)
                if plateau_terminal is not None:
                    self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                    stall_result = self._resolve_terminal_stall(plateau_terminal)
                    if stall_result is None:
                        self.attempt = 0
                        return "continue", None
                    return "return", stall_result
                self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                stall_result = self._resolve_terminal_stall(stall_pending)
                if stall_result is None:
                    self.attempt = 0
                    return "continue", None
                return "return", stall_result
        else:
            if self._maybe_expand_data():
                self.attempt = 0
                return "continue", None
            write_birth_progress(
                self.host.workspace_root,
                stage="history_unavailable",
                phase="data_expansion_exhausted",
                message="Birth research: max rollouts bereikt zonder patronen.",
                progress_pct=self.stage_progress_pct,
                cumulative_trades=self.host.cumulative_trades,
                target_trades=self.trade_budget_cap,
                birth_start_time=self.host.birth_start_time,
                retryable=True,
            )
            return (
                "return",
                history_unavailable_result(
                    total_trades=self.host.cumulative_trades,
                    ppo_steps=self.host.ppo_steps,
                ),
            )
        self.attempt = 0
        return "continue", None
