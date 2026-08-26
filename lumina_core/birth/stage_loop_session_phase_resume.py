"""_session_phase_resume extracted from StageLoopSessionRunnerMixin.run."""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.checkpoint import (
    load_checkpoint_state,
)
from lumina_core.birth.policy_swarm import PolicySwarmState
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session_runner")

__all__ = []


class SessionPhaseResumeMixin:
    """Sequential phase _session_phase_resume."""

    def _session_phase_resume(self):
        self.oracle_last_scanned = 0
        self.oracle_last_patterns = 0
        self.oracle_last_stop_pct = 0.0
        self.oracle_last_target_pct = 0.0
        self.oracle_last_reason = ""
        self._hard_stop_terminal_armed = False
        self._last_terminal_requested_log_at = 0.0
        self.current_intra_sample_pool: list[dict[str, Any]] = []
        self.active_train: list[dict[str, Any]] = []
        self.active_stage_ticks: list[dict[str, Any]] = []
        self._pending_deep_resume_harvest = False
        self.sim_ticks_processed_cumulative = 0
        self.rollout_wall_clock_total_sec = 0.0
        self.rollout_wall_clock_samples = 0
        self.evolution_last_action_applied: bool | None = None
        self.evolution_last_action_detail = ""
        self.provisional_pass_considered = False
        self.retries_this_stage = 0
        self.adaptation_tier = 0
        self.adaptation_history: list[dict[str, Any]] = []
        self.last_adaptation_stage_trades = -1
        self.adaptation_stuck_escapes = 0
        self.rollouts_since_last_adaptation = 0
        self._adaptation_stuck_train_grace_used = False
        self.swarm_state = PolicySwarmState()
        self.last_policy_entropy: float | None = None
        self.starship_exploration_burst_active = False
        self.swarm_tournament_at_start = -1.0
        self.swarm_tournament_lift_ok = False
        # Legacy aliases kept in sync for checkpoint/UI readers (Seal II).
        self.swarm_edgescore_at_start = -1.0
        self.swarm_edgescore_lift_ok = False
        self.swarm_rejected_no_lift = False
        self.swarm_retearnament_used = False
        self.swarm_champion_accepted = False
        self.swarm_fail_reason_code = ""
        self._swarm_reject_hard_stop_armed = False
        self.best_edgescore = 0.0
        self.best_edgescore_at_trade = 0
        self.best_edgescore_policy_path = ""
        self.oos_proxy_history: list[float] = []
        self.last_oos_proxy_at_trades = 0
        self.original_rollout_chunk = self.cur_cfg.rollout_chunk_trades
        self.stage_started_at = time.time()
        self.effective_trade_budget_cap = self.trade_budget_cap
        self.checkpoint_state = load_checkpoint_state(self.host.workspace_root)
        self.checkpoint_curriculum = str(self.checkpoint_state.get("curriculum_stage", "") or "").strip().lower()
        self.stage_metrics = self.checkpoint_state.get("stage_metrics")
        self.metrics_match_stage = (
            isinstance(self.stage_metrics, dict)
            and self.checkpoint_curriculum == self.stage.value
            and str(self.stage_metrics.get("curriculum_stage_scope", self.stage.value) or self.stage.value).strip().lower()
            == self.stage.value
        )
        if self.metrics_match_stage:
            self.patterns_mined = max(0, int(self.stage_metrics.get("patterns_mined", self.patterns_mined) or self.patterns_mined))
            self.stage_trades = max(0, int(self.stage_metrics.get("stage_trades", self.stage_trades) or self.stage_trades))
            self.stage_wins = max(0, int(self.stage_metrics.get("stage_wins", self.stage_wins) or self.stage_wins))
            self.stage_hold_signals = max(
                0, int(self.stage_metrics.get("stage_hold_signals", self.stage_hold_signals) or self.stage_hold_signals)
            )
            self.stage_total_signals = max(
                0, int(self.stage_metrics.get("stage_total_signals", self.stage_total_signals) or self.stage_total_signals)
            )
            self.stage_range_hold_signals = max(
                0,
                int(self.stage_metrics.get("stage_range_hold_signals", self.stage_range_hold_signals) or self.stage_range_hold_signals),
            )
            self.stage_range_total_signals = max(
                0,
                int(
                    self.stage_metrics.get("stage_range_total_signals", self.stage_range_total_signals)
                    or self.stage_range_total_signals
                ),
            )
            self.stage_range_flat_bars = max(
                0,
                int(self.stage_metrics.get("stage_range_flat_bars", self.stage_range_flat_bars) or self.stage_range_flat_bars),
            )
            self.stage_range_round_trips = max(
                0,
                int(
                    self.stage_metrics.get("stage_range_round_trips", self.stage_range_round_trips)
                    or self.stage_range_round_trips
                ),
            )
            raw_history = self.stage_metrics.get("winrate_history")
            if isinstance(raw_history, list):
                self.winrate_history = [float(x) for x in raw_history if isinstance(x, (int, float))]
            from lumina_core.birth.stage_loop_progress_metrics import (
                restore_stage_val_pnl,
                restore_stage_val_pnl_from_buffer,
                restore_stage_val_r,
                restore_stage_val_r_from_buffer,
            )

            self.stage_val_pnl = restore_stage_val_pnl(self.stage_metrics.get("stage_val_pnl"))
            buffer_trajs: list[Any] = []
            if not self.stage_val_pnl or not restore_stage_val_r(self.stage_metrics.get("stage_val_r")):
                host_buffer = getattr(self.host, "buffer", None)
                raw_trajs = getattr(host_buffer, "trajectories", None)
                if isinstance(raw_trajs, list) and raw_trajs:
                    buffer_trajs = raw_trajs
                else:
                    from lumina_core.birth.buffer_persist import load_buffer

                    buffer_trajs = load_buffer(self.host.workspace_root)
            if not self.stage_val_pnl:
                self.stage_val_pnl = restore_stage_val_pnl_from_buffer(
                    buffer_trajs,
                    stage_trades=int(self.stage_trades or 0),
                )
                if self.stage_val_pnl:
                    logger.info(
                        "birth.resume.stage_val_pnl_backfill n=%s stage_trades=%s",
                        len(self.stage_val_pnl),
                        int(self.stage_trades or 0),
                    )
            self.stage_val_r = restore_stage_val_r(self.stage_metrics.get("stage_val_r"))
            if not self.stage_val_r:
                self.stage_val_r = restore_stage_val_r_from_buffer(
                    buffer_trajs,
                    stage_trades=int(self.stage_trades or 0),
                )
                if self.stage_val_r:
                    logger.info(
                        "birth.resume.stage_val_r_backfill n=%s stage_trades=%s",
                        len(self.stage_val_r),
                        int(self.stage_trades or 0),
                    )
            raw_reward_history = self.stage_metrics.get("reward_history")
            if isinstance(raw_reward_history, list):
                self.reward_history = [float(x) for x in raw_reward_history if isinstance(x, (int, float))]
            self.low_velocity_attempts = max(
                0, int(self.stage_metrics.get("velocity_stall_attempts", self.low_velocity_attempts) or 0)
            )
            self.strong_recovery_mode = bool(self.stage_metrics.get("strong_recovery_mode", False))
            self.strong_recovery_attempts = max(
                0, int(self.stage_metrics.get("strong_recovery_attempts", 0) or 0)
            )
            self.retries_this_stage = max(0, int(self.stage_metrics.get("retries_this_stage", 0) or 0))
            self.adaptation_tier = max(0, int(self.stage_metrics.get("adaptation_tier", 0) or 0))
            raw_adaptations = self.stage_metrics.get("adaptation_history")
            if isinstance(raw_adaptations, list):
                self.adaptation_history = [dict(x) for x in raw_adaptations if isinstance(x, dict)]
            # Raptor v10: never force last_adaptation == stage_trades on resume
            # (that instantly re-arms adaptation_stuck before any train lap).
            if self.stage_metrics.get("rollouts_since_last_adaptation") is not None:
                self.rollouts_since_last_adaptation = max(
                    0,
                    int(self.stage_metrics.get("rollouts_since_last_adaptation", 0) or 0),
                )
            raw_milestones = self.stage_metrics.get("wins_at_trade_milestones")
            if isinstance(raw_milestones, dict) and raw_milestones:
                restored: dict[int, int] = {}
                for k, v in raw_milestones.items():
                    try:
                        restored[int(k)] = int(v)
                    except (TypeError, ValueError):
                        continue
                if restored:
                    self.wins_at_trade_milestones = restored
            # Seed current point so rolling window can form after ~window new trades.
            if self.stage_trades > 0 and self.stage_trades not in self.wins_at_trade_milestones:
                self.wins_at_trade_milestones[self.stage_trades] = self.stage_wins
            raw_chunks = self.stage_metrics.get("rolling_trade_chunks")
            if isinstance(raw_chunks, list) and raw_chunks:
                restored_chunks: list[tuple[int, int]] = []
                for item in raw_chunks:
                    try:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            restored_chunks.append((int(item[0]), int(item[1])))
                    except (TypeError, ValueError):
                        continue
                self.rolling_trade_chunks = restored_chunks
            if self.stage_metrics.get("escalation_level") is not None:
                self.escalation_level = max(0, int(self.stage_metrics.get("escalation_level", 0) or 0))
            # Restore Stage-2 peak capture so resume does not burn a truthful peak.
            raw_peak = self.stage_metrics.get("stage2_peak_state")
            if isinstance(raw_peak, dict) and raw_peak:
                try:
                    from lumina_core.birth.stage2_peak_capture import Stage2PeakState

                    st = Stage2PeakState(
                        peak_winrate=float(raw_peak.get("peak_winrate", 0.0) or 0.0),
                        peak_expectancy=float(raw_peak.get("peak_expectancy", -1.0) or -1.0),
                        peak_at_trade=int(raw_peak.get("peak_at_trade", 0) or 0),
                        peak_policy_path=str(raw_peak.get("peak_policy_path", "") or ""),
                        peak_flat=float(raw_peak.get("peak_flat", 0.0) or 0.0),
                        peak_edge_vs_random=float(
                            raw_peak.get("peak_edge_vs_random", 0.0) or 0.0
                        ),
                        near_miss_active=bool(raw_peak.get("near_miss_active", False)),
                        near_miss_count=int(raw_peak.get("near_miss_count", 0) or 0),
                        restore_count=int(raw_peak.get("restore_count", 0) or 0),
                        last_restore_at_trade=int(
                            raw_peak.get("last_restore_at_trade", 0) or 0
                        ),
                        last_restore_reason=str(
                            raw_peak.get("last_restore_reason", "") or ""
                        ),
                        quality_rollouts_since_restore=int(
                            raw_peak.get("quality_rollouts_since_restore", 0) or 0
                        ),
                        cumulative_closes_stop=int(
                            raw_peak.get("cumulative_closes_stop", 0) or 0
                        ),
                        cumulative_closes_target=int(
                            raw_peak.get("cumulative_closes_target", 0) or 0
                        ),
                        cumulative_closes_flatten=int(
                            raw_peak.get("cumulative_closes_flatten", 0) or 0
                        ),
                        cumulative_closes_time_stop=int(
                            raw_peak.get("cumulative_closes_time_stop", 0) or 0
                        ),
                        cumulative_closes_unknown=int(
                            raw_peak.get("cumulative_closes_unknown", 0) or 0
                        ),
                        peak_grad_armed=bool(raw_peak.get("peak_grad_armed", False)),
                        peak_grad_armed_at_trade=int(
                            raw_peak.get("peak_grad_armed_at_trade", 0) or 0
                        ),
                        volume_rechallenge_done=bool(
                            raw_peak.get("volume_rechallenge_done", False)
                        ),
                        volume_rechallenge_at_trade=int(
                            raw_peak.get("volume_rechallenge_at_trade", 0) or 0
                        ),
                        finish_mode_active=bool(
                            raw_peak.get("finish_mode_active", False)
                        ),
                        consecutive_rolling_pass_windows=int(
                            raw_peak.get("consecutive_rolling_pass_windows", 0) or 0
                        ),
                        flash_green=bool(raw_peak.get("flash_green", False)),
                        flash_green_wr=float(raw_peak.get("flash_green_wr", 0.0) or 0.0),
                        flash_green_at_trade=int(
                            raw_peak.get("flash_green_at_trade", 0) or 0
                        ),
                        flash_green_durable=bool(
                            raw_peak.get("flash_green_durable", False)
                        ),
                        consecutive_green_chunks=int(
                            raw_peak.get("consecutive_green_chunks", 0) or 0
                        ),
                        participation_force_exit_cum=int(
                            raw_peak.get("participation_force_exit_cum", 0) or 0
                        ),
                        quality_lock_active=bool(
                            raw_peak.get("quality_lock_active", False)
                        ),
                        quality_lock_wr=float(
                            raw_peak.get("quality_lock_wr", 0.0) or 0.0
                        ),
                        quality_lock_at_trade=int(
                            raw_peak.get("quality_lock_at_trade", 0) or 0
                        ),
                    )
                    self.stage2_peak_state = st
                except Exception:
                    pass
        return None
