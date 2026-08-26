"""Main stage-loop iteration body (while True). Public import: stage_loop_iteration.

Control flow stays here; heavy branches live in stall/pass/stagnation mixins + pure helpers.
"""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.plateau_escalator import should_trades_beyond_gate_hard_stop
from lumina_core.birth.stage_loop_iteration_helpers import failure_key_for_stage, wall_budget_elapsed
from lumina_core.birth.stage_loop_iteration_pass import StageLoopIterationPassMixin
from lumina_core.birth.stage_loop_iteration_stall import StageLoopIterationStallMixin
from lumina_core.birth.stage_loop_iteration_stagnation import StageLoopIterationStagnationMixin
from lumina_core.birth.stage_loop_iteration_swarm import (
    compute_rollout_chunk_target,
    heartbeat_progress_message,
    swarm_frozen_window_missing_message,
    swarm_hard_stop_progress_message,
    swarm_hard_stop_result,
)
from lumina_core.birth.stage_loop_rollout_cycle import StageLoopRolloutCycleMixin
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_iteration")


class StageLoopIterationMixin(
    StageLoopIterationStallMixin,
    StageLoopIterationPassMixin,
    StageLoopIterationStagnationMixin,
    StageLoopRolloutCycleMixin,
):
    """while-True curriculum iteration for StageLoopSession."""

    def _run_main_loop(self) -> dict[str, Any] | None:
        while True:
            if self.last_progress_write_at > 0 and time.time() - self.last_progress_write_at >= 60.0:
                self._write_progress(
                    phase="curriculum_learning",
                    message=heartbeat_progress_message(
                        stage_value=self.stage.value,
                        stage_trades=self.stage_trades,
                        required=self.required,
                        patterns_mined=self.patterns_mined,
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
                self._write_progress(
                    phase="paused",
                    message="Birth Phase gepauzeerd door gebruiker.",
                )
                return self.host._paused_result()

            # Starship Seal: after swarm reject, champion is sacred — no fresh-pool PPO.
            from lumina_core.birth.birth_control_plane import (
                should_hard_stop_training_after_swarm_reject,
            )

            if should_hard_stop_training_after_swarm_reject(
                swarm_state=self.swarm_state,
                host_rejected_no_lift=bool(getattr(self, "swarm_rejected_no_lift", False)),
                host_champion_accepted=bool(getattr(self, "swarm_champion_accepted", False)),
                retearnament_used=bool(getattr(self, "swarm_retearnament_used", False)),
                require_retearnament_before_hard_stop=True,
            ):
                if not bool(getattr(self, "_swarm_reject_hard_stop_armed", False)):
                    self._swarm_reject_hard_stop_armed = True
                    restore = getattr(self, "_restore_pre_swarm_policy", None)
                    if callable(restore):
                        try:
                            restore()
                        except Exception as exc:
                            logger.warning("birth.swarm.hard_stop_restore_failed: %s", exc)
                    if not str(getattr(self, "swarm_fail_reason_code", "") or "").strip():
                        self.swarm_fail_reason_code = "swarm_no_tournament_lift"
                    logger.warning(
                        "birth.swarm.hard_stop_training stage=%s reason=%s — accept or wipe",
                        self.stage.value,
                        getattr(self, "swarm_fail_reason_code", ""),
                    )
                    # App popup + Telegram same sacred questions (remote autonomy).
                    try:
                        from lumina_core.birth.champion_freeze_telegram import (
                            notify_champion_freeze_decision,
                        )

                        root = getattr(self.host, "workspace_root", None)
                        if root is not None:
                            notify_champion_freeze_decision(root, force=False)
                    except Exception as exc:
                        logger.debug("birth.swarm.freeze_telegram_notify_failed: %s", exc)
                self._write_progress(
                    phase="swarm_reject_hard_stop",
                    message=swarm_hard_stop_progress_message(),
                )
                self.host._persist_checkpoint(
                    training_mode=self.training_mode,
                    curriculum_stage=self.stage.value,
                    policy_path=str(self.host.final_policy_path),
                    phase="stage_stalled",
                    stage_metrics=self._stage_metrics_payload(),
                )
                return swarm_hard_stop_result(
                    total_trades=self.host.cumulative_trades,
                    ppo_steps=self.host.ppo_steps,
                    training_mode=self.training_mode,
                    reason_code=str(getattr(self, "swarm_fail_reason_code", "") or ""),
                )
            # First no-lift reject: arm re-tournament (hard-stop waits for retearnament_used).
            if bool(getattr(self, "swarm_rejected_no_lift", False)) and not bool(
                getattr(self, "swarm_retearnament_used", False)
            ):
                ensure_swarm = getattr(self, "_ensure_swarm_first", None)
                if callable(ensure_swarm):
                    try:
                        if ensure_swarm():
                            logger.info(
                                "birth.swarm.retearnament_armed stage=%s reason=%s",
                                self.stage.value,
                                getattr(self, "swarm_fail_reason_code", ""),
                            )
                            self._write_progress(
                                phase="policy_swarm",
                                message=(
                                    "Swarm rejected once — Starship re-tournament armed "
                                    "(one free ignition). Champion still sacred until lift."
                                ),
                            )
                    except Exception as exc:
                        logger.warning("birth.swarm.retearnament_arm_failed: %s", exc)

            elapsed_stage_sec = max(0.0, time.time() - self.stage_started_at)
            failure_key = failure_key_for_stage(self.stage)
            trades_beyond_hard_stop = should_trades_beyond_gate_hard_stop(
                self.stage_trades, self.required, self.cur_cfg
            )
            # H1: Stage-2 early-quality hard-stop — do not burn to 3× gate when already dead
            if not trades_beyond_hard_stop:
                try:
                    from lumina_core.birth.curriculum import CurriculumStage
                    from lumina_core.birth.expectancy_stall import (
                        should_stage2_early_quality_hard_stop,
                    )

                    if self.stage == CurriculumStage.STAGE2_RANGE:
                        rolling_wr = None
                        try:
                            rolling_wr, _, _ = self._rolling_winrate_meta()
                        except Exception:
                            rolling_wr = None
                        flat_ratio = float(self.stage_range_flat_bars) / float(
                            max(1, self.stage_range_total_signals)
                        )
                        if should_stage2_early_quality_hard_stop(
                            stage_is_range=True,
                            stage_trades=int(self.stage_trades),
                            required=int(self.required),
                            range_flat_ratio=flat_ratio,
                            stage_wins=int(self.stage_wins),
                            rolling_winrate=rolling_wr,
                            range_total_signals=int(self.stage_range_total_signals),
                            cfg=self.cur_cfg,
                        ):
                            # PR-E: freeze/restore — do not wall.force-spam every 50 trades.
                            freeze_on = bool(
                                getattr(
                                    self.cur_cfg,
                                    "stage2_early_quality_freeze_enabled",
                                    True,
                                )
                            )
                            cooldown = float(
                                getattr(
                                    self.cur_cfg,
                                    "stage2_early_quality_wall_cooldown_sec",
                                    300.0,
                                )
                                or 300.0
                            )
                            last_eq = float(
                                getattr(self, "_last_early_quality_wall_at", 0.0) or 0.0
                            )
                            now_eq = time.time()
                            if freeze_on:
                                try:
                                    from lumina_core.birth.stage2_peak_capture import (
                                        best_policy_path_for_restore,
                                        record_restore,
                                        restore_policy_from_path,
                                        should_restore_peak_policy,
                                    )

                                    peak_st = getattr(self, "stage2_peak_state", None)
                                    if peak_st is not None:
                                        peak_st.swarm_blocked_reason = "early_quality_freeze"
                                        # Freeze swarm for N quality rollouts after freeze.
                                        peak_st.quality_rollouts_since_restore = min(
                                            int(
                                                getattr(
                                                    peak_st,
                                                    "quality_rollouts_since_restore",
                                                    0,
                                                )
                                                or 0
                                            ),
                                            0,
                                        )
                                        do_r, rsn = should_restore_peak_policy(
                                            peak_st,
                                            stage_trades=int(self.stage_trades),
                                            stage_wins=int(self.stage_wins),
                                            rolling_winrate=rolling_wr,
                                            range_flat_ratio=flat_ratio,
                                            cfg=self.cur_cfg,
                                        )
                                        if do_r:
                                            path = best_policy_path_for_restore(
                                                peak_st,
                                                getattr(self, "plateau_state", None),
                                            )
                                            if path and restore_policy_from_path(
                                                self.host, path
                                            ):
                                                record_restore(
                                                    peak_st,
                                                    stage_trades=int(self.stage_trades),
                                                    reason=f"early_quality_{rsn}",
                                                )
                                    # Soft-stop active swarm tournament (no thrash).
                                    try:
                                        sw = getattr(self, "swarm_state", None)
                                        if sw is not None and bool(
                                            getattr(sw, "active", False)
                                        ):
                                            sw.active = False
                                            logger.info(
                                                "birth.stage2.early_quality_swarm_frozen"
                                            )
                                    except Exception:
                                        pass
                                except Exception:
                                    pass
                                # PR-H: never wall.force while peak_grad / near-miss finish.
                                peak_st = getattr(self, "stage2_peak_state", None)
                                no_wall = bool(
                                    peak_st is not None
                                    and (
                                        getattr(peak_st, "peak_grad_armed", False)
                                        or getattr(peak_st, "near_miss_active", False)
                                        or getattr(peak_st, "finish_mode_active", False)
                                        or getattr(peak_st, "flash_green_durable", False)
                                        or getattr(peak_st, "flash_green", False)
                                    )
                                )
                                if no_wall:
                                    logger.info(
                                        "birth.stage2.early_quality_no_wall peak_grad=%s "
                                        "near_miss=%s flash=%s trades=%s wr=%.3f",
                                        bool(
                                            getattr(peak_st, "peak_grad_armed", False)
                                        ),
                                        bool(
                                            getattr(peak_st, "near_miss_active", False)
                                        ),
                                        bool(getattr(peak_st, "flash_green", False)),
                                        self.stage_trades,
                                        float(self.stage_wins)
                                        / float(max(1, self.stage_trades)),
                                    )
                                # Rate-limit wall force: once per cooldown only.
                                elif now_eq - last_eq >= max(30.0, cooldown):
                                    trades_beyond_hard_stop = True
                                    self._last_early_quality_wall_at = now_eq
                                    logger.warning(
                                        "birth.stage2.early_quality_freeze trades=%s "
                                        "required=%s flat=%.3f wr=%.3f wall_armed=1",
                                        self.stage_trades,
                                        self.required,
                                        flat_ratio,
                                        float(self.stage_wins)
                                        / float(max(1, self.stage_trades)),
                                    )
                                else:
                                    logger.info(
                                        "birth.stage2.early_quality_freeze_hold trades=%s "
                                        "wr=%.3f cooldown_left=%.0fs",
                                        self.stage_trades,
                                        float(self.stage_wins)
                                        / float(max(1, self.stage_trades)),
                                        max(0.0, cooldown - (now_eq - last_eq)),
                                    )
                            else:
                                trades_beyond_hard_stop = True
                                logger.warning(
                                    "birth.stage2.early_quality_hard_stop trades=%s required=%s "
                                    "flat=%.3f wr=%.3f",
                                    self.stage_trades,
                                    self.required,
                                    flat_ratio,
                                    float(self.stage_wins)
                                    / float(max(1, self.stage_trades)),
                                )
                except Exception:
                    logger.debug("birth.stage2.early_quality_hard_stop_check_failed", exc_info=True)
            # Raptor v3: honor plateau terminal even when wall force never fires.
            if self.plateau_state.active:
                plateau_terminal = self._plateau_terminal_pending(failure_key=failure_key)
                if plateau_terminal is not None:
                    self._hard_stop_terminal_armed = True
                    # Rate-limit: terminal.requested was spamming every tick at trades=0.
                    _now = time.time()
                    _last = float(getattr(self, "_last_terminal_requested_log_at", 0.0) or 0.0)
                    if _now - _last >= 300.0:
                        self._last_terminal_requested_log_at = _now
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
                action, payload = self._iteration_handle_stall_pending(
                    stall_pending=stall_pending,
                    failure_key=failure_key,
                    trigger_type=trigger_type,
                    constitution_blocked=constitution_blocked,
                    trades_beyond_hard_stop=bool(trades_beyond_hard_stop),
                )
                if action == "continue":
                    continue
                if action == "return":
                    return payload
                # fallthrough → force_train_lap / rollout

            if wall_budget_elapsed(elapsed_stage_sec, int(self.cur_cfg.max_stage_wall_sec)):
                if (
                    len(self.host.buffer) >= 256
                    and self.host._constitution_guard.violations == 0
                    and (self.patterns_mined >= 100 or self.stage_trades >= 1)
                ):
                    if self.allow_provisional:
                        self.gen0_provisional = True
                        logger.info(
                            "birth.stage.wall_budget_provisional",
                            extra={
                                "event_data": {
                                    "stage": self.stage.value,
                                    "elapsed_sec": elapsed_stage_sec,
                                }
                            },
                        )
                    elif not self.wall_budget_exhausted:
                        self.wall_budget_exhausted = True
                        self.escalation_level = min(
                            self.cur_cfg.max_escalation_level, self.escalation_level + 1
                        )
                        logger.info(
                            "birth.stage.wall_budget_exhausted",
                            extra={
                                "event_data": {
                                    "stage": self.stage.value,
                                    "elapsed_sec": elapsed_stage_sec,
                                }
                            },
                        )
            # Starship: wall exhausted + skill fail → plateau/swarm, not soft explore forever.
            if self.wall_budget_exhausted and not self.allow_provisional:
                self._maybe_detect_plateau(
                    stage_trades=self.stage_trades, stage_wins=self.stage_wins
                )
                self._maybe_swarm_on_wall_skill_fail()

            action, payload = self._iteration_evaluate_and_handle_stage_pass()
            if action == "exit_stage":
                return None

            action, payload = self._iteration_handle_stagnation()
            if action == "continue":
                continue
            if action == "return":
                return payload

            action, payload = self._iteration_handle_max_rollouts()
            if action == "continue":
                continue
            if action == "return":
                return payload

            chunk_target = compute_rollout_chunk_target(
                stage_trades=self.stage_trades,
                required=self.required,
                rollout_chunk_trades=self.cur_cfg.rollout_chunk_trades,
            )
            # Starship B0: identical-window tournament — replay frozen slices.
            from lumina_core.birth.birth_control_plane import (
                fail_closed_missing_frozen_windows,
                require_frozen_windows_or_fail,
            )

            if bool(getattr(self.swarm_state, "active", False)):
                if not require_frozen_windows_or_fail(self.swarm_state):
                    fail_closed_missing_frozen_windows(self.swarm_state, host=self)
                    self.swarm_rejected_no_lift = True
                    self.swarm_fail_reason_code = "swarm_frozen_windows_missing"
                    logger.warning(
                        "birth.swarm.frozen_windows_missing stage=%s — fail-closed reject",
                        self.stage.value,
                    )
                    self._write_progress(
                        phase="swarm_frozen_windows_missing",
                        message=swarm_frozen_window_missing_message(empty=False),
                    )
                    continue
                next_win = getattr(self.swarm_state, "next_frozen_window", None)
                frozen = next_win() if callable(next_win) else None
                if not frozen:
                    fail_closed_missing_frozen_windows(self.swarm_state, host=self)
                    self.swarm_rejected_no_lift = True
                    self.swarm_fail_reason_code = "swarm_frozen_windows_missing"
                    logger.warning(
                        "birth.swarm.frozen_window_empty stage=%s — fail-closed reject",
                        self.stage.value,
                    )
                    self._write_progress(
                        phase="swarm_frozen_windows_missing",
                        message=swarm_frozen_window_missing_message(empty=True),
                    )
                    continue
                active_ticks = frozen
            else:
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
