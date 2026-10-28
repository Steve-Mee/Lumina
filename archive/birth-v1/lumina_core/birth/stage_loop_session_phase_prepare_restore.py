"""Session prepare: bus/progress/adaptation restore (M5)."""
from __future__ import annotations


from lumina_core.birth.progress import read_birth_progress
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session_runner")


class SessionPhasePrepareRestoreMixin:
    def _prepare_restore_bus_and_progress(self) -> None:
        """Restore bus states and progress counters."""
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

