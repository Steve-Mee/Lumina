"""Meta-controller value types (split from meta_controller for size)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from lumina_core.birth.config import BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage


@dataclass(frozen=True, slots=True)
class AdaptationDecision:
    should_retry: bool
    reason: str
    new_chunk_target: int
    escalation_increase: int = 1
    log_message: str = ""


@dataclass(frozen=True, slots=True)
class StallDetectionResult:
    is_stalled: bool
    winrate_velocity: float
    reward_velocity: float
    combined_velocity: float
    low_velocity_attempts: int
    threshold: int


class LearningHealth(str, Enum):
    IMPROVING = "improving"
    FLAT = "flat"
    DECLINING = "declining"


class RecoveryStrategy(str, Enum):
    HOLD = "hold"
    EXPLORE_BOOST = "explore_boost"
    EXPLORE_REDUCE = "explore_reduce"
    PATTERN_INJECT = "pattern_inject"
    PATTERN_INJECT_AGGRESSIVE = "pattern_inject_aggressive"
    DATA_EXPANSION = "data_expansion"
    REWARD_SHAPING_TWEAK = "reward_shaping_tweak"
    INTRA_EASE = "intra_ease"
    INTRA_RAMP = "intra_ramp"
    ADAPTATION_RETRY = "adaptation_retry"


@dataclass(frozen=True, slots=True)
class LearningSnapshot:
    winrate_history: tuple[float, ...]
    reward_history: tuple[float, ...]
    stage_trades: int
    required_trades: int
    patterns_mined: int
    patterns_last_inject: int
    oracle_wins_last_inject: int
    buffer_size: int
    escalation_level: int
    strong_recovery_mode: bool
    strong_recovery_attempts: int
    low_velocity_attempts: int
    data_exhausted: bool
    stage: CurriculumStage
    intra_hard_pct: float | None
    attempt: int = 0
    winrate_velocity: float = 0.0
    reward_velocity: float = 0.0
    combined_velocity: float = 0.0
    is_stalled: bool = False
    pattern_quality: float = 0.0
    learning_health: LearningHealth = LearningHealth.FLAT
    volume_gate_passed: bool = False
    range_flat_ratio: float = 0.0
    range_round_trips: int = 0
    constitution_violations: int = 0
    # Stage-2 expectancy quality ladder (Phase C) — optional snapshot fields.
    range_total_signals: int = 0
    plateau_active: bool = False
    expectancy_quality_step: int = 0
    stage_wins: int = 0
    rolling_winrate: float | None = None
    # Policy WR − first-touch thr (negative = worse than random entry).
    edge_vs_random: float | None = None
    median_loss_r: float | None = None

    @property
    def thin_buffer(self) -> bool:
        return self.buffer_size < 80


@dataclass(frozen=True, slots=True)
class MetaActionPlan:
    primary: RecoveryStrategy
    secondary: tuple[RecoveryStrategy, ...] = ()
    explore_steps: int | None = None
    explore_fraction: float | None = None
    chunk_target: int | None = None
    escalation_delta: int = 0
    mine: bool = False
    mine_aggressive: bool = False
    expand_data: bool = False
    reward_tweak: BirthRewardConfig | None = None
    intra_hard_pct_delta: float | None = None
    enter_strong_recovery: bool = False
    exit_strong_recovery: bool = False
    adaptation: AdaptationDecision | None = None
    explore_steps_multiplier: float = 1.0
    trigger: str = ""
    rationale: str = ""
    snapshot: LearningSnapshot | None = None
    suggest_provisional_pass: bool = False
    self_eval_phase: str = ""
    committed_strategy: str | None = None


def _with_trigger(plan: MetaActionPlan, trigger: str) -> MetaActionPlan:
    if plan.trigger == trigger:
        return plan
    return MetaActionPlan(
        primary=plan.primary,
        secondary=plan.secondary,
        explore_steps=plan.explore_steps,
        explore_fraction=plan.explore_fraction,
        chunk_target=plan.chunk_target,
        escalation_delta=plan.escalation_delta,
        mine=plan.mine,
        mine_aggressive=plan.mine_aggressive,
        expand_data=plan.expand_data,
        reward_tweak=plan.reward_tweak,
        intra_hard_pct_delta=plan.intra_hard_pct_delta,
        enter_strong_recovery=plan.enter_strong_recovery,
        exit_strong_recovery=plan.exit_strong_recovery,
        adaptation=plan.adaptation,
        explore_steps_multiplier=plan.explore_steps_multiplier,
        trigger=trigger,
        rationale=plan.rationale,
        snapshot=plan.snapshot,
        suggest_provisional_pass=plan.suggest_provisional_pass,
        self_eval_phase=plan.self_eval_phase,
        committed_strategy=plan.committed_strategy,
    )


