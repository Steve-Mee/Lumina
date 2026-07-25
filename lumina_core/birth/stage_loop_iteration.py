"""Main stage-loop iteration (while True body)."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.curriculum import (
    CurriculumStage,
    evaluate_stage_pass,
    should_gen0_soft_pass,
    stage_pass_trades,
)
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.plateau_escalator import (
    evolution_ladder_exhausted,
    should_trades_beyond_gate_hard_stop,
    should_trigger_plateau_evolution_step,
)
from lumina_core.birth.runway import risk_metrics_from_pnl
from lumina_core.birth.stage_loop_rollout_cycle import StageLoopRolloutCycleMixin
from lumina_core.birth.stage_pass_receipt import receipt_from_stage_result
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_iteration")


class StageLoopIterationMixin(StageLoopRolloutCycleMixin):
    """while-True curriculum iteration for StageLoopSession."""

    def _run_main_loop(self) -> dict[str, Any] | None:

        while True:
            if self.last_progress_write_at > 0 and time.time() - self.last_progress_write_at >= 60.0:
                self._write_progress(
                    phase="curriculum_learning",
                    message=(
                        f"Curriculum {self.stage.value}: heartbeat · {self.stage_trades:,} / "
                        f"{self.required:,} trades · patronen {self.patterns_mined:,}"
                    ),
                )

            if self.host._stop_requested():
                self.host._persist_checkpoint(
                    training_mode=self.training_mode,
                    curriculum_stage=self.stage.value,
                    policy_path=str(self.host.final_policy_path),
                    phase="paused",
                    stage_metrics=self._stage_metrics_payload(),
                )
                return self.host._paused_result()

            elapsed_stage_sec = max(0.0, time.time() - self.stage_started_at)
            failure_key = {
                CurriculumStage.STAGE1_TREND: "stage1_winrate",
                CurriculumStage.STAGE2_RANGE: "stage2_metric",
                # Raptor v9: stage3 is foundation floors (WR/hold), not constitution-only.
                CurriculumStage.STAGE3_MIXED: "stage3_foundation",
            }.get(self.stage, "stage_metrics")
            trades_beyond_hard_stop = should_trades_beyond_gate_hard_stop(
                self.stage_trades, self.required, self.cur_cfg
            )
            # Raptor v3: honor plateau terminal even when wall force never fires.
            if self.plateau_state.active:
                plateau_terminal = self._plateau_terminal_pending(failure_key=failure_key)
                if plateau_terminal is not None:
                    self._hard_stop_terminal_armed = True
                    logger.warning(
                        "birth.terminal.requested reason=%s step=%s trades=%s wr=%.2f%% beyond=%s",
                        plateau_terminal.get("terminal_stall_reason"),
                        self.plateau_state.evolution_step,
                        self.stage_trades,
                        float(self.stage_wins) / float(max(1, self.stage_trades)) * 100.0,
                        trades_beyond_hard_stop,
                    )
                    self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                    stall_result = self._resolve_terminal_stall(plateau_terminal)
                    if stall_result is None:
                        continue
                    logger.warning(
                        "birth.terminal.finalized reason=%s trades=%s",
                        plateau_terminal.get("terminal_stall_reason"),
                        self.stage_trades,
                    )
                    return stall_result
            wall_trigger = self._evaluate_wall_trigger(
                elapsed_stage_sec=elapsed_stage_sec,
                failure_key=failure_key,
                force=trades_beyond_hard_stop and self.stage_trades >= self.required,
            )
            stall_pending = None
            trigger_type = "certified_stall"
            constitution_blocked = False
            if wall_trigger is not None and wall_trigger.get("triggered"):
                pending = wall_trigger.get("pending")
                stall_pending = dict(pending) if isinstance(pending, dict) else None
                trigger_type = str(wall_trigger.get("trigger_type", "certified_stall"))
                constitution_blocked = bool(wall_trigger.get("constitution_blocked", False))
            if stall_pending is not None:
                beyond_gate = bool(
                    trades_beyond_hard_stop and self.stage_trades >= self.required
                )
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
                        continue
                    # Raptor v10: never terminal on first stuck without another train lap.
                    if self.plateau_state.active and self._try_plateau_evolution(
                        failure_key=failure_key
                    ):
                        self.rollouts_since_last_adaptation = 0
                        self.last_adaptation_stage_trades = -1
                        continue
                    if self._force_never_stop_recovery(failure_key=failure_key):
                        self.rollouts_since_last_adaptation = 0
                        self.last_adaptation_stage_trades = -1
                        continue
                    if not getattr(self, "_adaptation_stuck_train_grace_used", False):
                        self._adaptation_stuck_train_grace_used = True
                        self.rollouts_since_last_adaptation = 0
                        self.last_adaptation_stage_trades = -1
                        logger.warning(
                            "birth.adaptation.stuck_train_grace trades=%s — continue rollouts",
                            self.stage_trades,
                        )
                        continue
                    force_train_lap = True
                elif beyond_gate:
                    # Raptor v11: force wall + beyond-gate must not infinite-recover.
                    # Plateau awaits rollouts (0/12) while adaptive recovery was
                    # continue'ing every loop → stage_trades frozen (recovery cycling).
                    current_wr = float(self.stage_wins) / float(max(1, self.stage_trades))
                    if self.plateau_state.active and should_trigger_plateau_evolution_step(
                        self.plateau_state,
                        cfg=self.cur_cfg,
                        current_winrate=current_wr,
                        allow_start=False,
                        pass_target=self._plateau_pass_target(),
                        stage_trades=self.stage_trades,
                        required=self.required,
                    ) and self._try_plateau_evolution(failure_key=failure_key):
                        continue
                    if self.plateau_state.active and evolution_ladder_exhausted(
                        self.plateau_state
                    ):
                        if self._try_evolution_exhausted_remediation(failure_key=failure_key):
                            continue
                        plateau_terminal = self._plateau_terminal_pending(
                            failure_key=failure_key
                        )
                        if plateau_terminal is not None:
                            self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                            stall_result = self._resolve_terminal_stall(plateau_terminal)
                            if stall_result is None:
                                continue
                            return stall_result
                    evo_rollouts = int(
                        getattr(self.plateau_state, "evolution_rollouts_this_step", 0) or 0
                    )
                    evo_need = int(
                        getattr(self.cur_cfg, "plateau_evolution_rollouts_per_step", 12) or 12
                    )
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
                    continue
                if not force_train_lap:
                    current_wr = float(self.stage_wins) / float(max(1, self.stage_trades))
                    if self.plateau_state.active and should_trigger_plateau_evolution_step(
                        self.plateau_state,
                        cfg=self.cur_cfg,
                        current_winrate=current_wr,
                        allow_start=False,
                        pass_target=self._plateau_pass_target(),
                        stage_trades=self.stage_trades,
                        required=self.required,
                    ) and self._try_plateau_evolution(failure_key=failure_key):
                        continue
                    if not adaptation_stuck and self._force_never_stop_recovery(
                        failure_key=failure_key
                    ):
                        continue
                    if self.plateau_state.active and self._try_plateau_evolution(
                        failure_key=failure_key
                    ):
                        continue
                    if self.plateau_state.active and evolution_ladder_exhausted(
                        self.plateau_state
                    ):
                        if self._try_evolution_exhausted_remediation(failure_key=failure_key):
                            continue
                    plateau_terminal = self._plateau_terminal_pending(failure_key=failure_key)
                    if plateau_terminal is not None:
                        self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                        stall_result = self._resolve_terminal_stall(plateau_terminal)
                        if stall_result is None:
                            continue
                        return stall_result
                    self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                    stall_result = self._resolve_terminal_stall(stall_pending)
                    if stall_result is None:
                        continue
                    return stall_result
                # force_train_lap: fall through to rollout body below

            if elapsed_stage_sec >= max(300, int(self.cur_cfg.max_stage_wall_sec)):
                if (
                    len(self.host.buffer) >= 256
                    and self.host._constitution_guard.violations == 0
                    and (self.patterns_mined >= 100 or self.stage_trades >= 1)
                ):
                    if self.allow_provisional:
                        self.gen0_provisional = True
                        logger.info(
                            "birth.stage.wall_budget_provisional",
                            extra={"event_data": {"stage": self.stage.value, "elapsed_sec": elapsed_stage_sec}},
                        )
                    elif not self.wall_budget_exhausted:
                        self.wall_budget_exhausted = True
                        self.escalation_level = min(self.cur_cfg.max_escalation_level, self.escalation_level + 1)
                        logger.info(
                            "birth.stage.wall_budget_exhausted",
                            extra={"event_data": {"stage": self.stage.value, "elapsed_sec": elapsed_stage_sec}},
                        )

            stage_val_sharpe = 0.0
            stage_val_max_dd = 100.0
            if self.stage_val_pnl:
                stage_val_sharpe, stage_val_max_dd = risk_metrics_from_pnl(self.stage_val_pnl)
            # Raptor v12/v13: rolling WR for stage1+stage3; only trust real window.
            rolling_wr: float | None = None
            if self.stage in (
                CurriculumStage.STAGE1_TREND,
                CurriculumStage.STAGE3_MIXED,
            ):
                try:
                    wr, source, covered = self._rolling_winrate_meta()
                    window = int(getattr(self.cur_cfg, "stage1_rolling_pass_window", 500) or 500)
                    min_for_pass = min(400, window)
                    # Do not use lifetime-fallback as a fake "OR rolling" path.
                    if source in ("true_window", "partial_window") and covered >= min_for_pass:
                        rolling_wr = float(wr)
                    else:
                        rolling_wr = None
                except Exception:
                    rolling_wr = None
            stage_result = evaluate_stage_pass(
                self.stage,
                trades=self.stage_trades,
                wins=self.stage_wins,
                hold_signals=self.stage_hold_signals,
                total_signals=self.stage_total_signals,
                range_hold_signals=self.stage_range_hold_signals,
                range_total_signals=self.stage_range_total_signals,
                range_flat_bars=self.stage_range_flat_bars,
                range_round_trips=self.stage_range_round_trips,
                constitution_violations=self.host._constitution_guard.violations,
                target_trades=self.target,
                cfg=self.cur_cfg,
                provisional=self.gen0_provisional,
                allow_provisional=self.allow_provisional,
                oracle_patterns=self.patterns_mined,
                buffer_size=len(self.host.buffer),
                stage_val_sharpe=stage_val_sharpe,
                stage_val_max_drawdown_pct=stage_val_max_dd,
                rolling_winrate=rolling_wr,
            )
            if stage_result.passed:
                self.required = stage_pass_trades(self.stage, self.cur_cfg)
                pass_winrate = float(self.stage_wins) / float(max(1, self.stage_trades))
                logger.info(
                    "birth.stage.passed stage=%s trades=%s wins=%s required=%s "
                    "winrate=%.2f%% provisional=%s reason=%s",
                    self.stage.value,
                    self.stage_trades,
                    self.stage_wins,
                    self.required,
                    pass_winrate * 100.0,
                    bool(stage_result.provisional),
                    stage_result.message,
                    extra={
                        "event_data": {
                            "stage": self.stage.value,
                            "trades": self.stage_trades,
                            "wins": self.stage_wins,
                            "required": self.required,
                            "winrate": round(pass_winrate, 4),
                            "patterns_mined": self.patterns_mined,
                            "attempts": self.attempt,
                            "pass_reason": stage_result.message,
                            "provisional": stage_result.provisional,
                        }
                    },
                )
                self.host._pending_stage_pass_receipt = receipt_from_stage_result(
                    self.stage,
                    stage_result,
                    cfg=self.cur_cfg,
                    hold_signals=self.stage_hold_signals,
                    total_signals=self.stage_total_signals,
                    range_hold_signals=self.stage_range_hold_signals,
                    range_total_signals=self.stage_range_total_signals,
                    range_flat_bars=self.stage_range_flat_bars,
                )
                return None

            if self.stage_trades == self.last_stage_trades:
                self.stagnation_count += 1
            else:
                self.stagnation_count = 0
                self.last_stage_trades = self.stage_trades

            if self.stagnation_count >= self.cur_cfg.stagnation_rollouts_before_expand:
                self._mine_and_inject()
                if not self._maybe_expand_data():
                    if self.allow_provisional and (
                        self.stage_trades > 0 or self.patterns_mined > 0 or len(self.host.buffer) >= 256
                    ):
                        self.gen0_provisional = True
                        continue
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
                        return {
                            "status": "history_unavailable",
                            "total_trades": self.host.cumulative_trades,
                            "ppo_steps": self.host.ppo_steps,
                            "training_mode": "certified",
                        }
                self.stagnation_count = 0
                if len(self.host.buffer) >= 80:
                    self.host.current_policy = self.host.ppo_trainer.update_from_buffer(
                        buffer=self.host.buffer,
                        timesteps=self.ppo_steps_per_update,
                        birth_phase=True,
                    )
                    self.host.ppo_steps += self.ppo_steps_per_update

            if self.attempt >= self._effective_max_rollouts():
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
                    force_failure_key = {
                        CurriculumStage.STAGE1_TREND: "stage1_winrate",
                        CurriculumStage.STAGE2_RANGE: "stage2_metric",
                        CurriculumStage.STAGE3_MIXED: "stage3_constitution",
                    }.get(self.stage, "stage_metrics")
                    stall_pending = self._would_certified_stage_stall(
                        elapsed_stage_sec=time.time() - self.stage_started_at,
                        failure_key=force_failure_key,
                        force=True,
                    )
                    if stall_pending is not None:
                        if self._try_adaptive_stall_recovery(failure_key=force_failure_key):
                            self.attempt = 0
                            continue
                        force_wr = float(self.stage_wins) / float(max(1, self.stage_trades))
                        if self.plateau_state.active and should_trigger_plateau_evolution_step(
                            self.plateau_state,
                            cfg=self.cur_cfg,
                            current_winrate=force_wr,
                            allow_start=False,
                            pass_target=self._plateau_pass_target(),
                        ) and self._try_plateau_evolution(failure_key=force_failure_key):
                            self.attempt = 0
                            continue
                        if self._force_never_stop_recovery(failure_key=force_failure_key):
                            self.attempt = 0
                            continue
                        if self.plateau_state.active and self._try_plateau_evolution(
                            failure_key=force_failure_key
                        ):
                            self.attempt = 0
                            continue
                        plateau_terminal = self._plateau_terminal_pending(
                            failure_key=force_failure_key
                        )
                        if plateau_terminal is not None:
                            self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                            stall_result = self._resolve_terminal_stall(plateau_terminal)
                            if stall_result is None:
                                self.attempt = 0
                                continue
                            return stall_result
                        self.cur_cfg.rollout_chunk_trades = self.original_rollout_chunk
                        stall_result = self._resolve_terminal_stall(stall_pending)
                        if stall_result is None:
                            self.attempt = 0
                            continue
                        return stall_result
                else:
                    if self._maybe_expand_data():
                        self.attempt = 0
                        continue
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
                    return {
                        "status": "history_unavailable",
                        "total_trades": self.host.cumulative_trades,
                        "ppo_steps": self.host.ppo_steps,
                        "training_mode": "certified",
                    }
                self.attempt = 0
                continue

            if self.stage_trades >= self.required:
                chunk_target = self.cur_cfg.rollout_chunk_trades
            else:
                remaining = max(1, self.required - self.stage_trades)
                chunk_target = min(remaining, self.cur_cfg.rollout_chunk_trades)
            active_ticks = self.host._stage_tick_pool(
                stage=self.stage,
                stage_ticks=self.active_stage_ticks,
                train_ticks=self.active_train,
                escalation_level=self.escalation_level,
                attempt=self.attempt,
                chunk_target=chunk_target,
                cur_cfg=self.cur_cfg,
                intra_state=self.intra_state,
                easy_pool=self.intra_easy_pool,
                hard_pool=self.intra_hard_pool,
                intra_s2_state=self.intra_s2_state,
                s2_easy_pool=self.intra_s2_easy_pool,
                s2_hard_pool=self.intra_s2_hard_pool,
            )
            self.current_intra_sample_pool = list(active_ticks)

            terminal = self._execute_rollout_cycle(
                active_ticks=active_ticks,
                chunk_target=chunk_target,
            )
            if terminal is not None:
                return terminal
        return None
