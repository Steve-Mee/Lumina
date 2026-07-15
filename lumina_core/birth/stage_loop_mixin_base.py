"""Shared attribute declarations for StageLoopSession mixins (mypy)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lumina_core.birth.birth_bus_client import BirthBusClient
    from lumina_core.birth.curriculum import CurriculumStage
    from lumina_core.birth.policy_swarm import PolicySwarmState

    class StageLoopMixinBase:
        host: Any
        stage: CurriculumStage
        stage_ticks: list[dict[str, Any]]
        train_ticks: list[dict[str, Any]]
        holdout_ticks: list[dict[str, Any]]
        target: int
        trade_budget_cap: int
        cur_cfg: Any
        bus: BirthBusClient
        required: int
        allow_provisional: bool
        stage_trades: int
        stage_wins: int
        patterns_mined: int
        attempt: int
        escalation_level: int
        expansion_step: int
        hold_stagnation_count: int
        winrate_stagnation_count: int
        wall_budget_exhausted: bool
        hold_trap_milestone_sent: bool
        over_trading_milestone_sent: bool
        last_range_flat_ratio: float
        last_policy_rollback_attempt: int
        low_velocity_attempts: int
        strong_recovery_mode: bool
        strong_recovery_attempts: int
        last_adaptation_stage_trades: int
        effective_trade_budget_cap: int
        last_oos_proxy_at_trades: int
        last_stage_trades: int
        stagnation_count: int
        active_train: list[dict[str, Any]]
        active_stage_ticks: list[dict[str, Any]]
        data_exhausted: bool
        scorecard_snapshot_trades: int
        scorecard_snapshot_patterns: int
        scorecard_snapshot_at: float
        last_winrate: float
        last_hold_ratio: float
        swarm_state: PolicySwarmState
        chunk_trades_snapshot: int
        plateau_state: Any
        wa_state: Any
else:

    class StageLoopMixinBase:
        """Marker base for stage-loop mixins."""
