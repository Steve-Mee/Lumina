"""_session_phase_init extracted from StageLoopSessionRunnerMixin.run."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.curriculum import (
    stage_pass_trades,
)
from lumina_core.birth.foundation_history import foundation_history_start_days
from lumina_core.birth.stage_scorecard import (
    learning_metric_target,
    pass_criteria_for_stage,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage_loop_session_runner")

__all__: list[str] = []


class SessionPhaseInitMixin:
    """Sequential phase _session_phase_init."""

    def _session_phase_init(self):
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
        self.allow_provisional = False
        from lumina_core.birth.foundation_stages import foundation_eval_only

        self._foundation_eval_only = foundation_eval_only(self.stage)
        self.max_rollouts = (
            1
            if self._foundation_eval_only
            else (
                self.cur_cfg.max_rollouts_per_stage
                if self.training_mode == "practice"
                else min(
                    self.cur_cfg.max_rollouts_per_stage,
                    self.cur_cfg.certified_max_rollouts_per_stage,
                )
            )
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
        self._foundation_epoch_count = 0
        self._foundation_epoch_hash = ""
        self.escalation_level = 0
        self.gen0_provisional = False
        self.patterns_mined = 0
        self.oracle_wins = 0
        self.expansion_step = 0
        self.data_days_loaded = int(
            (self.host._data_manifest or {}).get("requested_days")
            or foundation_history_start_days()
        )
        self.hold_stagnation_count = 0
        self.winrate_stagnation_count = 0
        self.wall_budget_exhausted = False
        self.winrate_history: list[float] = []
        self.stage_val_pnl: list[float] = []
        self.stage_val_r: list[float] = []
        self._unique_calendar_days = 0
        try:
            from lumina_core.birth.history_loader import session_unique_calendar_days

            self._unique_calendar_days = session_unique_calendar_days(
                cached=0,
                host=self.host,
                ticks=self.stage_ticks,
            )
        except Exception:
            self._unique_calendar_days = 0
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
        # Fresh peak-capture state per stage session (no stale WR from prior stage).
        try:
            from lumina_core.birth.stage2_peak_capture import Stage2PeakState

            self.stage2_peak_state = Stage2PeakState()
        except Exception:
            self.stage2_peak_state = None
        self._occupancy_control_window: list[int] = []
        self.occupancy_control_flat = 0.0
        self.occupancy_in_band_seen = False
        self.occupancy_seed_source = "n/a"
        self.occupancy_seed_value = None
        from lumina_core.birth.s5_occupancy_continuity import apply_s5_occupancy_seed

        apply_s5_occupancy_seed(self)
        return None
