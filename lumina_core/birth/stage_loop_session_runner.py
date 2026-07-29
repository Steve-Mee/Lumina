"""StageLoopSessionRunnerMixin — session.run() body (Wave B PR-B4).

Keeps StageLoopSession as composition root; heavy init/resume lives here.
"""
from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.checkpoint import (
    apply_plateau_quarantine_on_checkpoint_resume,
    load_checkpoint_state,
)
from lumina_core.birth.curriculum import (
    CurriculumStage,
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
    stage1_intra_state_from_metrics,
    stage1_winrate_pass_threshold,
    stage2_intra_state_from_metrics,
    stage_pass_trades,
)
from lumina_core.birth.meta_controller import MetaActionPlan
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
from lumina_core.birth.progress import read_birth_progress
from lumina_core.birth.stage_scorecard import (
    learning_metric_target,
    pass_criteria_for_stage,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session_runner")

__all__ = ["StageLoopSessionRunnerMixin"]


class StageLoopSessionRunnerMixin:
    """Owns StageLoopSession.run(); see StageLoopSession for attributes."""

    def run(self) -> dict[str, Any] | None:
        self.holdout_ticks_ref = list(self.holdout_ticks)
        self.cur_cfg = self.host.birth_config.curriculum
        self.bus: BirthBusClient | None = getattr(self.host, "_birth_bus_client", None)
        if self.bus is None and getattr(self.host, "event_bus", None) is not None:
            twin = None
            if hasattr(self.host, "_resolve_approval_twin"):
                try:
                    twin = self.host._resolve_approval_twin()
                except Exception:
                    twin = None
            self.bus = BirthBusClient(
                self.host.event_bus,
                self.cur_cfg,
                self.host.birth_config.reward,
                approval_twin=twin,
            )
            self.host._birth_bus_client = self.bus
        elif self.bus is not None and hasattr(self.host, "_resolve_approval_twin"):
            # Late-bind twin if host acquired it after initial bus create
            try:
                twin = self.host._resolve_approval_twin()
                if twin is not None and hasattr(self.bus.registry, "bind_approval_twin"):
                    self.bus.registry.bind_approval_twin(twin)
            except Exception:
                pass
        if self.bus is None:
            raise RuntimeError("BirthBusClient required for stage rollout executor")
        self.bus.cfg = self.cur_cfg
        self.bus.registry.sync_curriculum_cfg(self.cur_cfg)

        self.news_cfg = self.host.birth_config.news
        self.required = stage_pass_trades(self.stage, self.cur_cfg)
        self.stage_pass_criteria = pass_criteria_for_stage(self.stage, cfg=self.cur_cfg)
        self.pass_metric_target = learning_metric_target(
            self.stage,
            cfg=self.cur_cfg,
            pass_criteria=self.stage_pass_criteria,
        )
        # Certified never soft-graduates (config flag alone cannot bypass hard gates).
        self.allow_provisional = self.training_mode == "practice"
        self.max_rollouts = (
            self.cur_cfg.max_rollouts_per_stage
            if self.allow_provisional
            else min(self.cur_cfg.max_rollouts_per_stage, self.cur_cfg.certified_max_rollouts_per_stage)
        )
        self.stage_trades = 0
        self.stage_wins = 0
        self.stage_hold_signals = 0
        self.stage_total_signals = 0
        self.stage_range_hold_signals = 0
        self.stage_range_total_signals = 0
        self.stage_range_flat_bars = 0
        self.stage_range_round_trips = 0
        self.attempt = 0
        self.escalation_level = 0
        self.gen0_provisional = False
        self.patterns_mined = 0
        self.oracle_wins = 0
        self.expansion_step = 0
        self.data_days_loaded = self.host.birth_config.max_real_days
        self.hold_stagnation_count = 0
        self.winrate_stagnation_count = 0
        self.wall_budget_exhausted = False
        self.winrate_history: list[float] = []
        self.stage_val_pnl: list[float] = []
        self.budget_milestones_notified: set[int] = set()
        self.hold_trap_milestone_sent = False
        self.over_trading_milestone_sent = False
        self.last_range_flat_ratio = 0.0
        self.last_policy_rollback_attempt = -999
        self.reward_history: list[float] = []
        self.low_velocity_attempts = 0
        self.strong_recovery_mode = False
        self.strong_recovery_attempts = 0
        self.plateau_quarantine: dict[str, Any] = {
            "plateau_quarantine_active": False,
            "plateau_quarantine_rollouts_remaining": 0,
            "plateau_quarantine_trades_remaining": 0,
            "plateau_quarantine_trades_at_resume": 0,
        }
        self.ppo_steps_at_plateau_evolution_step = 0
        self.wins_at_trade_milestones: dict[int, int] = {}
        self.rolling_trade_chunks: list[tuple[int, int]] = []
        self._rolling_winrate_source = "lifetime_fallback"
        self._rolling_window_trades_covered = 0
        self.oracle_last_scanned = 0
        self.oracle_last_patterns = 0
        self.oracle_last_stop_pct = 0.0
        self.oracle_last_target_pct = 0.0
        self.oracle_last_reason = ""
        self._hard_stop_terminal_armed = False
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
        self.bus.restore_states(
            stage=self.stage,
            stage_metrics=self.stage_metrics if isinstance(self.stage_metrics, dict) else None,
        )
        self.plateau_state = self.bus.plateau_state
        self.remediation_state = self.bus.remediation_state
        self.organism_autonomy_state = self.bus.autonomy_state
        self.wa_state = self.bus.wall_adaptation_state
        self.retries_this_stage = int(self.wa_state.retries_this_stage)
        self.adaptation_tier = int(self.wa_state.adaptation_tier)
        self.escalation_level = int(self.wa_state.escalation_level)
        self.adaptation_history = list(self.wa_state.adaptation_history)
        self.last_adaptation_stage_trades = int(self.wa_state.last_adaptation_stage_trades)
        self.adaptation_stuck_escapes = int(self.wa_state.adaptation_stuck_escapes)
        self.rollouts_since_last_adaptation = max(
            0,
            int(getattr(self.wa_state, "rollouts_since_last_adaptation", 0) or 0),
            int(getattr(self, "rollouts_since_last_adaptation", 0) or 0),
        )
        # Resume grace: if adaptation left trades frozen, require fresh train laps.
        if (
            self.last_adaptation_stage_trades == self.stage_trades
            and self.stage_trades >= self.required
        ):
            self.rollouts_since_last_adaptation = 0
            if hasattr(self.wa_state, "rollouts_since_last_adaptation"):
                self.wa_state.rollouts_since_last_adaptation = 0
        self.prev_progress = read_birth_progress(self.host.workspace_root)
        if str(self.prev_progress.get("curriculum_stage", "") or "").strip().lower() == self.stage.value:
            self.stage_trades = max(0, int(self.prev_progress.get("stage_trades", 0) or 0))
            if self.prev_progress.get("stage_wins") is not None:
                self.stage_wins = max(0, int(self.prev_progress.get("stage_wins", 0) or 0))
            self.stage_hold_signals = max(0, int(self.prev_progress.get("stage_hold_signals", 0) or 0))
            self.stage_total_signals = max(0, int(self.prev_progress.get("stage_total_signals", 0) or 0))
            self.stage_range_flat_bars = max(0, int(self.prev_progress.get("stage_range_flat_bars", 0) or 0))
            self.stage_range_round_trips = max(0, int(self.prev_progress.get("stage_range_round_trips", 0) or 0))
            self.stage_range_total_signals = max(
                0, int(self.prev_progress.get("stage_range_total_signals", 0) or 0)
            )
            self.patterns_mined = max(0, int(self.prev_progress.get("patterns_mined", 0) or 0))
            self.oracle_wins = max(0, int(self.prev_progress.get("oracle_wins", 0) or 0))
            self.attempt = max(0, int(self.prev_progress.get("learning_attempt", 0) or 0) - 1)
            self.escalation_level = max(0, int(self.prev_progress.get("escalation_level", 0) or 0))
            self.gen0_provisional = bool(self.prev_progress.get("gen0_provisional", False))
            self.expansion_step = max(0, int(self.prev_progress.get("expansion_step", 0) or 0))
            self.data_days_loaded = max(
                0,
                int(self.prev_progress.get("data_days_loaded", self.data_days_loaded) or self.data_days_loaded),
            )
        if self.adaptation_history:
            last_chunk = self.adaptation_history[-1].get("chunk_target")
            if last_chunk is not None:
                self.cur_cfg.rollout_chunk_trades = max(
                    self.cur_cfg.exploration_chunk_size,
                    int(last_chunk),
                )
        elif self.strong_recovery_mode:
            self.cur_cfg.rollout_chunk_trades = max(
                self.cur_cfg.exploration_chunk_size,
                self.cur_cfg.exploration_chunk_size * 2,
            )
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
        self.last_stage_trades = -1
        self.stagnation_count = 0
        self.chunk_budget = max(5_000, self.cur_cfg.rollout_chunk_trades * self.cur_cfg.rollout_step_budget_multiplier)
        self.active_train = list(self.train_ticks)
        self.active_stage_ticks = list(self.stage_ticks)
        # Raptor v9: harvest only after tick pools exist.
        if getattr(self, "_pending_deep_resume_harvest", False):
            self._pending_deep_resume_harvest = False
            try:
                self._force_oracle_harvest(reason="deep_resume")
            except Exception as exc:
                logger.warning("birth.oracle.force_harvest_failed: %s", exc)
        self.data_exhausted = False
        self.scorecard_snapshot_trades = self.stage_trades
        self.scorecard_snapshot_patterns = self.patterns_mined
        self.scorecard_snapshot_at = time.time()
        self.last_progress_write_at = 0.0
        self.last_hold_ratio = 0.0



        self.intra_state: Stage1IntraCurriculumState | None = None
        self.intra_easy_pool: list[dict[str, Any]] = []
        self.intra_hard_pool: list[dict[str, Any]] = []
        self.intra_meta: dict[str, Any] = {}
        self.intra_s2_state: Stage2IntraCurriculumState | None = None
        self.intra_s2_easy_pool: list[dict[str, Any]] = []
        self.intra_s2_hard_pool: list[dict[str, Any]] = []
        self.intra_s2_meta: dict[str, Any] = {}
        self.current_intra_sample_pool: list[dict[str, Any]] = []


        if self.stage == CurriculumStage.STAGE1_TREND and self.cur_cfg.intra_stage1_enabled:
            if isinstance(self.stage_metrics, dict) and self.stage_metrics.get("intra_stage1_hard_pct") is not None:
                self.intra_state = stage1_intra_state_from_metrics(
                    self.stage_metrics,
                    default_hard_pct=self.cur_cfg.intra_initial_hard_pct,
                )
            else:
                self.intra_state = Stage1IntraCurriculumState(hard_pct=self.cur_cfg.intra_initial_hard_pct)
            self._rebuild_intra_pools(self.active_stage_ticks)
        if self.stage == CurriculumStage.STAGE2_RANGE and self.cur_cfg.intra_stage2_enabled:
            if isinstance(self.stage_metrics, dict) and self.stage_metrics.get("intra_stage2_hard_pct") is not None:
                self.intra_s2_state = stage2_intra_state_from_metrics(
                    self.stage_metrics,
                    default_hard_pct=self.cur_cfg.intra_stage2_initial_hard_pct,
                )
            else:
                self.intra_s2_state = Stage2IntraCurriculumState(
                    hard_pct=self.cur_cfg.intra_stage2_initial_hard_pct
                )
            self._rebuild_intra_pools(self.active_stage_ticks)
        self.last_winrate = 0.0
        self.meta_last_plan: MetaActionPlan | None = None
        self.meta_message_suffix = ""

















        self._write_progress(
            phase="curriculum_research",
            message=f"Curriculum {self.stage.value}: oracle scan start (doel {self.required:,} trades).",
        )
        if isinstance(self.stage_metrics, dict) and self.stage_metrics.get("pending_data_expand"):
            self._maybe_expand_data()
            pending_cleared = dict(self._stage_metrics_payload())
            pending_cleared.pop("pending_data_expand", None)
            self.host._persist_checkpoint(
                training_mode=self.training_mode,
                curriculum_stage=self.stage.value,
                policy_path=str(self.host.final_policy_path),
                phase="curriculum_learning",
                stage_metrics=pending_cleared,
            )
        self._mine_and_inject()
        if len(self.host.buffer) >= 80:
            self.host.current_policy = self.host.ppo_trainer.update_from_buffer(
                buffer=self.host.buffer,
                timesteps=self.ppo_steps_per_update,
                birth_phase=True,
            )
            self.host.ppo_steps += self.ppo_steps_per_update
            self._capture_trainer_policy_entropy()
































        return self._run_main_loop()
