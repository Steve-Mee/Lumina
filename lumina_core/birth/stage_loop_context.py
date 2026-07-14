"""Stage loop mutable state container for birth curriculum rollout."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.birth.curriculum import (
    Stage1IntraCurriculumState,
    Stage2IntraCurriculumState,
)
from lumina_core.birth.meta_controller import MetaActionPlan
from lumina_core.birth.policy_swarm import PolicySwarmState


@dataclass
class StageLoopContext:
    """Mutable stage-loop counters and pools (replaces closure nonlocals)."""

    stage_trades: int = 0
    stage_wins: int = 0
    stage_hold_signals: int = 0
    stage_total_signals: int = 0
    stage_range_hold_signals: int = 0
    stage_range_total_signals: int = 0
    stage_range_flat_bars: int = 0
    stage_range_round_trips: int = 0
    attempt: int = 0
    escalation_level: int = 0
    gen0_provisional: bool = False
    patterns_mined: int = 0
    oracle_wins: int = 0
    expansion_step: int = 0
    data_days_loaded: int = 0
    hold_stagnation_count: int = 0
    winrate_stagnation_count: int = 0
    wall_budget_exhausted: bool = False
    winrate_history: list[float] = field(default_factory=list)
    stage_val_pnl: list[float] = field(default_factory=list)
    budget_milestones_notified: set[int] = field(default_factory=set)
    hold_trap_milestone_sent: bool = False
    over_trading_milestone_sent: bool = False
    last_range_flat_ratio: float = 0.0
    last_policy_rollback_attempt: int = -999
    reward_history: list[float] = field(default_factory=list)
    low_velocity_attempts: int = 0
    strong_recovery_mode: bool = False
    strong_recovery_attempts: int = 0
    plateau_quarantine: dict[str, Any] = field(default_factory=dict)
    ppo_steps_at_plateau_evolution_step: int = 0
    wins_at_trade_milestones: dict[int, int] = field(default_factory=dict)
    sim_ticks_processed_cumulative: int = 0
    rollout_wall_clock_total_sec: float = 0.0
    rollout_wall_clock_samples: int = 0
    evolution_last_action_applied: bool | None = None
    evolution_last_action_detail: str = ""
    provisional_pass_considered: bool = False
    retries_this_stage: int = 0
    adaptation_tier: int = 0
    adaptation_history: list[dict[str, Any]] = field(default_factory=list)
    last_adaptation_stage_trades: int = -1
    adaptation_stuck_escapes: int = 0
    swarm_state: PolicySwarmState = field(default_factory=PolicySwarmState)
    oos_proxy_history: list[float] = field(default_factory=list)
    last_oos_proxy_at_trades: int = 0
    original_rollout_chunk: int = 0
    stage_started_at: float = 0.0
    effective_trade_budget_cap: int = 0
    last_stage_trades: int = -1
    stagnation_count: int = 0
    chunk_budget: int = 0
    data_exhausted: bool = False
    scorecard_snapshot_trades: int = 0
    scorecard_snapshot_patterns: int = 0
    scorecard_snapshot_at: float = 0.0
    last_progress_write_at: float = 0.0
    last_hold_ratio: float = 0.0
    last_winrate: float = 0.0
    meta_last_plan: MetaActionPlan | None = None
    meta_message_suffix: str = ""
    intra_state: Stage1IntraCurriculumState | None = None
    intra_easy_pool: list[dict[str, Any]] = field(default_factory=list)
    intra_hard_pool: list[dict[str, Any]] = field(default_factory=list)
    intra_meta: dict[str, Any] = field(default_factory=dict)
    intra_s2_state: Stage2IntraCurriculumState | None = None
    intra_s2_easy_pool: list[dict[str, Any]] = field(default_factory=list)
    intra_s2_hard_pool: list[dict[str, Any]] = field(default_factory=list)
    intra_s2_meta: dict[str, Any] = field(default_factory=dict)
    current_intra_sample_pool: list[dict[str, Any]] = field(default_factory=list)
    active_train: list[dict[str, Any]] = field(default_factory=list)
    active_stage_ticks: list[dict[str, Any]] = field(default_factory=list)
    best_policy_path: Path | None = None

    def trade_budget_remaining(self, host: Any) -> int:
        return max(0, int(self.effective_trade_budget_cap) - int(host.cumulative_trades))


__all__ = ["StageLoopContext"]