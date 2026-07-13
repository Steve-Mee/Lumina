"""Birth Phase meta-controller: learning observation, recovery strategy, curriculum nudges."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_self_eval import (
    ProvisionalFallbackResult,
    SelfEvalPhase,
    SelfEvalState,
    StrategyProbeResult,
    build_probe_queue,
    score_probe_result,
    select_winner,
    should_start_self_eval,
)
from lumina_core.birth.stage_scorecard import calculate_simple_slope, combined_learning_velocity


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


def get_adaptation_decision(
    *,
    stage_trades: int,
    required: int,
    winrate: float,
    winrate_history: list[float],
    escalation_level: int,
    cfg: BirthCurriculumConfig,
) -> AdaptationDecision:
    """High-leverage rule: recent winrate trend after volume gate has been passed."""
    _ = winrate
    if len(winrate_history) >= 5:
        slope = (winrate_history[-1] - winrate_history[0]) / max(1, len(winrate_history) - 1)
    else:
        slope = 0.0

    is_negative_trend = slope < cfg.negative_slope_threshold

    if stage_trades >= required and is_negative_trend:
        new_chunk = min(25, cfg.exploration_chunk_size * (1 + escalation_level))
        return AdaptationDecision(
            should_retry=True,
            reason="negative_winrate_trend_after_volume_gate",
            new_chunk_target=new_chunk,
            escalation_increase=1,
            log_message=(
                f"Negative trend (slope={slope:.4f}). Boosting exploration to chunk={new_chunk}"
            ),
        )

    if stage_trades >= required:
        return AdaptationDecision(
            should_retry=True,
            reason="metrics_not_improving_within_wall",
            new_chunk_target=cfg.exploration_chunk_size,
            escalation_increase=1,
            log_message="Metrics stalled after volume gate. Applying exploration boost.",
        )

    return AdaptationDecision(
        should_retry=True,
        reason="default_stall_retry",
        new_chunk_target=cfg.rollout_chunk_trades,
        escalation_increase=1,
        log_message="Standard stall recovery.",
    )


def detect_stall(
    *,
    winrate_history: list[float],
    reward_history: list[float],
    low_velocity_attempts: int,
    cfg: BirthCurriculumConfig,
    oos_proxy_history: list[float] | None = None,
) -> StallDetectionResult:
    """Detect learning stall from combined winrate and reward velocity trends."""
    winrate_velocity = calculate_simple_slope(winrate_history)
    reward_velocity = calculate_simple_slope(reward_history)
    if oos_proxy_history:
        from lumina_core.birth.oos_proxy import blended_learning_velocity

        combined = blended_learning_velocity(
            winrate_history=winrate_history,
            reward_history=reward_history,
            oos_proxy_history=oos_proxy_history,
            cfg=cfg,
        )
    else:
        combined = combined_learning_velocity(winrate_history, reward_history)

    threshold = int(cfg.velocity_stall_attempt_threshold)
    epsilon = float(cfg.velocity_stall_epsilon)
    min_samples = max(3, int(getattr(cfg, "velocity_stall_min_history_samples", 5)))
    if (
        len(winrate_history) < min_samples
        or len(reward_history) < min_samples
    ):
        return StallDetectionResult(
            is_stalled=low_velocity_attempts >= threshold,
            winrate_velocity=winrate_velocity,
            reward_velocity=reward_velocity,
            combined_velocity=combined,
            low_velocity_attempts=low_velocity_attempts,
            threshold=threshold,
        )
    if combined <= epsilon:
        updated_attempts = low_velocity_attempts + 1
    else:
        updated_attempts = 0

    return StallDetectionResult(
        is_stalled=updated_attempts >= threshold,
        winrate_velocity=winrate_velocity,
        reward_velocity=reward_velocity,
        combined_velocity=combined,
        low_velocity_attempts=updated_attempts,
        threshold=threshold,
    )


def _classify_learning_health(combined_velocity: float, cfg: BirthCurriculumConfig) -> LearningHealth:
    epsilon = float(cfg.velocity_stall_epsilon)
    improving_threshold = epsilon * float(cfg.meta_improving_velocity_multiplier)
    if combined_velocity > improving_threshold:
        return LearningHealth.IMPROVING
    if combined_velocity < -epsilon:
        return LearningHealth.DECLINING
    return LearningHealth.FLAT


def _pattern_quality(patterns_last_inject: int, oracle_wins_last_inject: int) -> float:
    if patterns_last_inject <= 0:
        return 0.0
    return float(oracle_wins_last_inject) / float(patterns_last_inject)


def _hold_plan(snap: LearningSnapshot, rationale: str = "") -> MetaActionPlan:
    return MetaActionPlan(
        primary=RecoveryStrategy.HOLD,
        rationale=rationale or "learning_on_track",
        snapshot=snap,
    )


def _recovery_from_str(strategy: str) -> RecoveryStrategy:
    for item in RecoveryStrategy:
        if item.value == strategy:
            return item
    return RecoveryStrategy.HOLD


@dataclass(slots=True)
class BirthMetaController:
    """Observe birth learning signals and recommend recovery / curriculum adjustments."""

    cfg: BirthCurriculumConfig
    baseline_reward: BirthRewardConfig
    active_reward: BirthRewardConfig = field(init=False)
    strategy_history: list[dict[str, Any]] = field(default_factory=list)
    patterns_last_inject: int = 0
    oracle_wins_last_inject: int = 0
    explore_multiplier: float = 1.0
    last_review_trigger: str = ""
    rollouts_since_review: int = 0
    self_eval: SelfEvalState = field(default_factory=SelfEvalState)
    self_eval_history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.active_reward = replace(self.baseline_reward)
        self.explore_multiplier = max(0.4, min(1.0, float(self.explore_multiplier)))

    @property
    def enabled(self) -> bool:
        return bool(self.cfg.meta_controller_enabled)

    @property
    def reward_tweak_active(self) -> bool:
        return self.active_reward.expectancy_coeff != self.baseline_reward.expectancy_coeff

    def restore_state(self, metrics: dict[str, Any] | None) -> None:
        if not isinstance(metrics, dict):
            return
        self.patterns_last_inject = max(
            0, int(metrics.get("meta_patterns_last_inject", self.patterns_last_inject) or 0)
        )
        self.oracle_wins_last_inject = max(
            0,
            int(metrics.get("meta_oracle_wins_last_inject", self.oracle_wins_last_inject) or 0),
        )
        raw_history = metrics.get("meta_strategy_history")
        if isinstance(raw_history, list):
            self.strategy_history = [dict(x) for x in raw_history if isinstance(x, dict)]
        tweaked = metrics.get("meta_reward_expectancy_coeff")
        if tweaked is not None:
            coeff = float(tweaked)
            self.active_reward = replace(
                self.baseline_reward,
                expectancy_coeff=min(
                    float(self.cfg.meta_max_expectancy_coeff),
                    max(self.baseline_reward.expectancy_coeff, coeff),
                ),
            )
        explore_raw = metrics.get("meta_explore_multiplier")
        if explore_raw is not None:
            self.explore_multiplier = max(0.4, min(1.0, float(explore_raw)))
        trigger_raw = metrics.get("meta_review_trigger")
        if trigger_raw is not None:
            self.last_review_trigger = str(trigger_raw)
        self.rollouts_since_review = max(
            0, int(metrics.get("meta_rollouts_since_review", self.rollouts_since_review) or 0)
        )
        self.self_eval = SelfEvalState.from_metrics(metrics)
        raw_self_eval_history = metrics.get("meta_self_eval_history")
        if isinstance(raw_self_eval_history, list):
            self.self_eval_history = [
                dict(x) for x in raw_self_eval_history if isinstance(x, dict)
            ]

    def metrics_payload(self) -> dict[str, Any]:
        return {
            "meta_patterns_last_inject": int(self.patterns_last_inject),
            "meta_oracle_wins_last_inject": int(self.oracle_wins_last_inject),
            "meta_strategy_history": list(self.strategy_history[-20:]),
            "meta_reward_expectancy_coeff": round(float(self.active_reward.expectancy_coeff), 4),
            "meta_reward_tweak_active": bool(self.reward_tweak_active),
            "meta_explore_multiplier": round(float(self.explore_multiplier), 4),
            "meta_review_trigger": str(self.last_review_trigger),
            "meta_rollouts_since_review": int(self.rollouts_since_review),
            "meta_self_eval_history": list(self.self_eval_history[-10:]),
            **self.self_eval.to_metrics(),
        }

    def record_inject(self, *, patterns: int, oracle_wins: int) -> None:
        self.patterns_last_inject = max(0, int(patterns))
        self.oracle_wins_last_inject = max(0, int(oracle_wins))

    def observe(
        self,
        *,
        winrate_history: list[float],
        reward_history: list[float],
        stage_trades: int,
        required_trades: int,
        patterns_mined: int,
        buffer_size: int,
        escalation_level: int,
        strong_recovery_mode: bool,
        strong_recovery_attempts: int,
        low_velocity_attempts: int,
        data_exhausted: bool,
        stage: CurriculumStage,
        intra_hard_pct: float | None,
        attempt: int = 0,
        range_flat_ratio: float = 0.0,
        range_round_trips: int = 0,
        oos_proxy_history: list[float] | None = None,
    ) -> tuple[LearningSnapshot, StallDetectionResult]:
        stall = detect_stall(
            winrate_history=winrate_history,
            reward_history=reward_history,
            low_velocity_attempts=low_velocity_attempts,
            cfg=self.cfg,
            oos_proxy_history=oos_proxy_history,
        )
        quality = _pattern_quality(self.patterns_last_inject, self.oracle_wins_last_inject)
        health = _classify_learning_health(stall.combined_velocity, self.cfg)
        snap = LearningSnapshot(
            winrate_history=tuple(winrate_history),
            reward_history=tuple(reward_history),
            stage_trades=stage_trades,
            required_trades=required_trades,
            patterns_mined=patterns_mined,
            patterns_last_inject=self.patterns_last_inject,
            oracle_wins_last_inject=self.oracle_wins_last_inject,
            buffer_size=buffer_size,
            escalation_level=escalation_level,
            strong_recovery_mode=strong_recovery_mode,
            strong_recovery_attempts=strong_recovery_attempts,
            low_velocity_attempts=stall.low_velocity_attempts,
            data_exhausted=data_exhausted,
            stage=stage,
            intra_hard_pct=intra_hard_pct,
            attempt=attempt,
            winrate_velocity=stall.winrate_velocity,
            reward_velocity=stall.reward_velocity,
            combined_velocity=stall.combined_velocity,
            is_stalled=stall.is_stalled,
            pattern_quality=round(quality, 4),
            learning_health=health,
            volume_gate_passed=stage_trades >= required_trades,
            range_flat_ratio=float(range_flat_ratio),
            range_round_trips=int(range_round_trips),
        )
        return snap, stall

    def _apply_reward_tweak(self, snap: LearningSnapshot) -> BirthRewardConfig | None:
        if snap.learning_health == LearningHealth.IMPROVING:
            if self.reward_tweak_active:
                self.active_reward = replace(self.baseline_reward)
                return replace(self.baseline_reward)
            return None
        if (
            snap.learning_health == LearningHealth.DECLINING
            and snap.reward_velocity < 0.0
            and snap.volume_gate_passed
        ):
            step = float(self.cfg.meta_reward_tweak_step)
            cap = float(self.cfg.meta_max_expectancy_coeff)
            new_coeff = min(cap, self.active_reward.expectancy_coeff + step)
            if new_coeff > self.active_reward.expectancy_coeff:
                self.active_reward = replace(self.active_reward, expectancy_coeff=new_coeff)
                return replace(self.active_reward)
        return None

    def decide_pre_rollout(
        self,
        snap: LearningSnapshot,
        *,
        base_explore_steps: int,
        wall_budget_exhausted: bool,
        winrate_stagnation_count: int,
        hold_stagnation_count: int,
        over_trading_trap: bool = False,
    ) -> MetaActionPlan:
        if not self.enabled:
            return MetaActionPlan(
                primary=RecoveryStrategy.HOLD,
                explore_steps=base_explore_steps,
                snapshot=snap,
            )

        explore_steps = base_explore_steps
        explore_fraction: float | None = None
        escalation_delta = 0
        primary = RecoveryStrategy.HOLD
        secondary: list[RecoveryStrategy] = []
        rationale = "default_rollout"

        if snap.strong_recovery_mode:
            explore_fraction = float(self.cfg.strong_recovery_explore_fraction)
            explore_steps = max(
                200,
                int(self.cfg.exploration_steps * explore_fraction),
            )
            primary = RecoveryStrategy.EXPLORE_REDUCE
            rationale = "strong_recovery_exploit"
        elif wall_budget_exhausted:
            explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
            primary = RecoveryStrategy.EXPLORE_BOOST
            escalation_delta = 1
            rationale = "wall_budget_exhausted"
        elif (
            snap.stage == CurriculumStage.STAGE2_RANGE
            and snap.volume_gate_passed
            and hold_stagnation_count >= self.cfg.stage2_hold_stagnation_rollouts
        ):
            explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
            primary = RecoveryStrategy.EXPLORE_BOOST
            escalation_delta = 1
            rationale = "stage2_hold_stagnation"
        elif snap.stage == CurriculumStage.STAGE2_RANGE and snap.volume_gate_passed:
            if over_trading_trap:
                explore_steps = max(
                    200,
                    int(self.cfg.exploration_steps * self.cfg.strong_recovery_explore_fraction),
                )
                primary = RecoveryStrategy.EXPLORE_REDUCE
                escalation_delta = 1
                rationale = "stage2_over_trading"
        elif (
            snap.stage == CurriculumStage.STAGE1_TREND
            and snap.volume_gate_passed
            and winrate_stagnation_count >= self.cfg.stage1_winrate_stagnation_rollouts
        ):
            explore_steps = max(explore_steps, self.cfg.exploration_steps * 4)
            primary = RecoveryStrategy.EXPLORE_BOOST
            secondary.append(RecoveryStrategy.PATTERN_INJECT)
            escalation_delta = 1
            rationale = "stage1_winrate_stagnation"

        if snap.learning_health == LearningHealth.IMPROVING and not snap.strong_recovery_mode:
            escalation_delta = min(escalation_delta, -1)

        return MetaActionPlan(
            primary=primary,
            secondary=tuple(secondary),
            explore_steps=explore_steps,
            explore_fraction=explore_fraction,
            escalation_delta=escalation_delta,
            mine=RecoveryStrategy.PATTERN_INJECT in secondary,
            rationale=rationale,
            snapshot=snap,
        )

    def decide_after_rollout(self, snap: LearningSnapshot) -> MetaActionPlan:
        if not self.enabled:
            return _hold_plan(snap, "meta_controller_disabled")

        if snap.learning_health == LearningHealth.IMPROVING and snap.volume_gate_passed:
            reward_tweak = self._apply_reward_tweak(snap)
            if snap.strong_recovery_mode:
                return MetaActionPlan(
                    primary=RecoveryStrategy.HOLD,
                    exit_strong_recovery=True,
                    chunk_target=max(
                        self.cfg.exploration_chunk_size,
                        self.cfg.rollout_chunk_trades,
                    ),
                    reward_tweak=reward_tweak,
                    rationale="velocity_recovered",
                    snapshot=snap,
                )
            return MetaActionPlan(
                primary=RecoveryStrategy.HOLD,
                reward_tweak=reward_tweak,
                rationale="improving_learning",
                snapshot=snap,
            )

        if not snap.is_stalled:
            return _hold_plan(snap)

        primary = RecoveryStrategy.EXPLORE_BOOST
        secondary: list[RecoveryStrategy] = []
        mine = False
        mine_aggressive = False
        expand_data = False
        enter_strong = False
        escalation_delta = 0
        chunk_target: int | None = None
        intra_delta: float | None = None
        reward_tweak: BirthRewardConfig | None = None
        rationale = "velocity_stall"

        if snap.thin_buffer and not snap.data_exhausted:
            primary = RecoveryStrategy.DATA_EXPANSION
            expand_data = True
            rationale = "stall_thin_buffer_expand_data"
        elif snap.pattern_quality < float(self.cfg.meta_pattern_yield_floor):
            primary = RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE
            mine = True
            mine_aggressive = True
            rationale = "stall_low_pattern_yield"
        elif snap.volume_gate_passed:
            primary = RecoveryStrategy.EXPLORE_REDUCE
            enter_strong = True
            escalation_delta = int(self.cfg.strong_recovery_escalation_boost)
            chunk_target = max(
                self.cfg.exploration_chunk_size,
                self.cfg.exploration_chunk_size * 2,
            )
            mine = True
            mine_aggressive = True
            rationale = "stall_enter_strong_recovery"
        else:
            primary = RecoveryStrategy.EXPLORE_BOOST
            secondary.append(RecoveryStrategy.PATTERN_INJECT)
            mine = True
            escalation_delta = 1
            rationale = "stall_pre_volume_gate"

        if (
            snap.pattern_quality >= float(self.cfg.meta_pattern_yield_floor)
            and snap.winrate_velocity <= 0.0
        ):
            secondary.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
            reward_tweak = self._apply_reward_tweak(snap)

        if (
            snap.learning_health == LearningHealth.FLAT
            and snap.volume_gate_passed
            and snap.stage == CurriculumStage.STAGE1_TREND
            and snap.intra_hard_pct is not None
            and snap.intra_hard_pct > self.cfg.intra_initial_hard_pct
        ):
            intra_delta = -float(self.cfg.intra_hard_pct_step)
            secondary.append(RecoveryStrategy.INTRA_EASE)

        if snap.strong_recovery_mode:
            expand_every = int(self.cfg.strong_recovery_expand_every_attempts)
            if snap.strong_recovery_attempts > 0 and snap.strong_recovery_attempts % expand_every == 0:
                expand_data = True
                mine = True
                mine_aggressive = True
                if RecoveryStrategy.DATA_EXPANSION not in secondary:
                    secondary.append(RecoveryStrategy.DATA_EXPANSION)

        plan = MetaActionPlan(
            primary=primary,
            secondary=tuple(dict.fromkeys(secondary)),
            chunk_target=chunk_target,
            escalation_delta=escalation_delta,
            mine=mine,
            mine_aggressive=mine_aggressive,
            expand_data=expand_data,
            reward_tweak=reward_tweak,
            intra_hard_pct_delta=intra_delta,
            enter_strong_recovery=enter_strong and not snap.strong_recovery_mode,
            explore_steps_multiplier=1.0 if enter_strong else self.explore_multiplier,
            rationale=rationale,
            snapshot=snap,
        )
        if enter_strong and not snap.strong_recovery_mode:
            self.explore_multiplier = max(
                0.4,
                min(1.0, float(self.cfg.meta_explore_decay_stall)),
            )
        self._record_plan(plan)
        return plan

    def decide_periodic_review(self, snap: LearningSnapshot) -> MetaActionPlan:
        if not self.enabled:
            return _hold_plan(snap, "meta_controller_disabled")

        if snap.learning_health == LearningHealth.IMPROVING:
            secondary: list[RecoveryStrategy] = []
            intra_delta: float | None = None
            decay = max(
                0.4,
                min(1.0, float(self.cfg.meta_explore_decay_improving)),
            )
            rationale = "periodic_improving_explore_decay"
            if (
                self.cfg.meta_intra_ramp_on_improving
                and snap.stage == CurriculumStage.STAGE1_TREND
                and snap.intra_hard_pct is not None
                and snap.intra_hard_pct < self.cfg.intra_max_hard_pct
            ):
                intra_delta = float(self.cfg.intra_hard_pct_step)
                secondary.append(RecoveryStrategy.INTRA_RAMP)
                rationale = "periodic_improving_ramp_and_decay"
            plan = MetaActionPlan(
                primary=RecoveryStrategy.EXPLORE_REDUCE,
                secondary=tuple(secondary),
                explore_steps_multiplier=decay,
                intra_hard_pct_delta=intra_delta,
                rationale=rationale,
                snapshot=snap,
            )
            self.explore_multiplier = decay
            self._record_plan(plan)
            return plan

        if snap.learning_health == LearningHealth.DECLINING:
            mine = True
            mine_aggressive = snap.pattern_quality < float(self.cfg.meta_pattern_yield_floor)
            primary = (
                RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE
                if mine_aggressive
                else RecoveryStrategy.PATTERN_INJECT
            )
            reward_tweak = self._apply_reward_tweak(snap)
            secondary: list[RecoveryStrategy] = []
            if reward_tweak is not None:
                secondary.append(RecoveryStrategy.REWARD_SHAPING_TWEAK)
            plan = MetaActionPlan(
                primary=primary,
                secondary=tuple(secondary),
                mine=mine,
                mine_aggressive=mine_aggressive,
                reward_tweak=reward_tweak,
                rationale="periodic_declining_pattern_focus",
                snapshot=snap,
            )
            self._record_plan(plan)
            return plan

        if (
            snap.learning_health == LearningHealth.FLAT
            and snap.stage == CurriculumStage.STAGE1_TREND
            and snap.intra_hard_pct is not None
            and snap.intra_hard_pct > self.cfg.intra_initial_hard_pct
        ):
            plan = MetaActionPlan(
                primary=RecoveryStrategy.INTRA_EASE,
                intra_hard_pct_delta=-float(self.cfg.intra_hard_pct_step),
                rationale="periodic_flat_intra_ease",
                snapshot=snap,
            )
            self._record_plan(plan)
            return plan

        if snap.thin_buffer and not snap.data_exhausted:
            plan = MetaActionPlan(
                primary=RecoveryStrategy.DATA_EXPANSION,
                expand_data=True,
                rationale="periodic_thin_buffer_expand",
                snapshot=snap,
            )
            self._record_plan(plan)
            return plan

        return _hold_plan(snap, "periodic_no_action_needed")

    def decide_review(
        self,
        snap: LearningSnapshot,
        *,
        trigger: str,
        base_explore_steps: int = 0,
        wall_budget_exhausted: bool = False,
        winrate_stagnation_count: int = 0,
        hold_stagnation_count: int = 0,
    ) -> MetaActionPlan:
        self.last_review_trigger = str(trigger)
        self.rollouts_since_review = 0
        if trigger == "pre_rollout":
            plan = self.decide_pre_rollout(
                snap,
                base_explore_steps=base_explore_steps,
                wall_budget_exhausted=wall_budget_exhausted,
                winrate_stagnation_count=winrate_stagnation_count,
                hold_stagnation_count=hold_stagnation_count,
            )
            return _with_trigger(plan, trigger)
        if trigger == "stall":
            if snap.is_stalled or snap.strong_recovery_mode:
                plan = self.decide_after_rollout(snap)
            else:
                plan = self.decide_periodic_review(snap)
            return _with_trigger(plan, trigger)
        if trigger == "adaptation":
            return _hold_plan(snap, "adaptation_handled_separately")
        plan = self.decide_periodic_review(snap)
        return _with_trigger(plan, trigger)

    @staticmethod
    def format_decision_log(plan: MetaActionPlan, *, trigger: str = "") -> dict[str, Any]:
        snap = plan.snapshot
        return {
            "trigger": trigger or plan.trigger,
            "primary": plan.primary.value,
            "secondary": [s.value for s in plan.secondary],
            "rationale": plan.rationale,
            "learning_health": snap.learning_health.value if snap else LearningHealth.FLAT.value,
            "combined_velocity": round(snap.combined_velocity, 6) if snap else 0.0,
            "winrate_velocity": round(snap.winrate_velocity, 6) if snap else 0.0,
            "reward_velocity": round(snap.reward_velocity, 6) if snap else 0.0,
            "pattern_quality": snap.pattern_quality if snap else 0.0,
            "is_stalled": bool(snap.is_stalled) if snap else False,
            "actions": {
                "mine": plan.mine,
                "mine_aggressive": plan.mine_aggressive,
                "expand_data": plan.expand_data,
                "enter_strong_recovery": plan.enter_strong_recovery,
                "exit_strong_recovery": plan.exit_strong_recovery,
                "explore_steps_multiplier": round(plan.explore_steps_multiplier, 4),
                "intra_hard_pct_delta": plan.intra_hard_pct_delta,
                "escalation_delta": plan.escalation_delta,
            },
        }

    def apply_explore_multiplier(self, explore_steps: int) -> int:
        mult = max(0.4, min(1.0, float(self.explore_multiplier)))
        return max(200, int(explore_steps * mult))

    def decide_adaptation(
        self,
        snap: LearningSnapshot,
        *,
        winrate: float,
        escalation_level: int,
        adaptation_tier: int,
        retries_this_stage: int,
        original_rollout_chunk: int,
        failure_key: str,
    ) -> MetaActionPlan:
        adaptation = get_adaptation_decision(
            stage_trades=snap.stage_trades,
            required=snap.required_trades,
            winrate=winrate,
            winrate_history=list(snap.winrate_history),
            escalation_level=escalation_level,
            cfg=self.cfg,
        )
        if not adaptation.should_retry and adaptation_tier == 0 and retries_this_stage == 0:
            adaptation = AdaptationDecision(
                should_retry=True,
                reason="stall_escalation",
                new_chunk_target=max(
                    self.cfg.exploration_chunk_size,
                    min(self.cfg.rollout_chunk_trades * 2, original_rollout_chunk),
                ),
                escalation_increase=1,
                log_message="Escalation ladder: forced recovery at stall boundary",
            )
        if not adaptation.should_retry and adaptation_tier >= 1:
            adaptation = AdaptationDecision(
                should_retry=True,
                reason="persistent_recovery",
                new_chunk_target=max(
                    self.cfg.exploration_chunk_size,
                    self.cfg.rollout_chunk_trades,
                ),
                escalation_increase=0,
                log_message=(
                    f"Persistent recovery tier {adaptation_tier + 1}/"
                    f"{self.cfg.max_adaptation_tiers}"
                ),
            )

        mine = adaptation_tier >= 1
        expand_data = adaptation_tier >= 2 and self.cfg.auto_expand_on_adaptation
        secondary: list[RecoveryStrategy] = [RecoveryStrategy.ADAPTATION_RETRY]
        if mine:
            secondary.append(RecoveryStrategy.PATTERN_INJECT)
        if expand_data:
            secondary.append(RecoveryStrategy.DATA_EXPANSION)

        plan = MetaActionPlan(
            primary=RecoveryStrategy.ADAPTATION_RETRY,
            secondary=tuple(secondary),
            chunk_target=adaptation.new_chunk_target if adaptation.should_retry else None,
            escalation_delta=adaptation.escalation_increase if adaptation.should_retry else 0,
            mine=mine,
            expand_data=expand_data,
            adaptation=adaptation if adaptation.should_retry else None,
            rationale=f"adaptation_{failure_key}",
            snapshot=snap,
        )
        if adaptation.should_retry:
            self._record_plan(plan)
        return plan

    def scorecard_fields(self, plan: MetaActionPlan | None = None) -> dict[str, Any]:
        snap = plan.snapshot if plan and plan.snapshot else None
        return {
            **self.metrics_payload(),
            "meta_primary_strategy": (
                plan.primary.value if plan else RecoveryStrategy.HOLD.value
            ),
            "meta_learning_health": (
                snap.learning_health.value if snap else LearningHealth.FLAT.value
            ),
            "meta_pattern_quality": snap.pattern_quality if snap else 0.0,
            "meta_explore_multiplier": round(float(self.explore_multiplier), 4),
            "meta_review_trigger": str(self.last_review_trigger),
        }

    def is_self_eval_active(self) -> bool:
        if not self.cfg.meta_self_eval_enabled:
            return False
        return self.self_eval.phase in (
            SelfEvalPhase.PROBING,
            SelfEvalPhase.COMMITTED,
            SelfEvalPhase.EXHAUSTED,
        )

    def maybe_start_self_eval(
        self,
        snap: LearningSnapshot,
        *,
        strong_recovery_attempts: int,
        attempt: int,
    ) -> bool:
        if not should_start_self_eval(
            snap,
            self.self_eval,
            self.cfg,
            strong_recovery_attempts=strong_recovery_attempts,
            attempt=attempt,
        ):
            return False
        queue = build_probe_queue(snap, self.cfg)
        if not queue:
            return False
        self.self_eval = SelfEvalState(
            phase=SelfEvalPhase.PROBING,
            probe_queue=list(queue),
            current_strategy=queue[0],
            rollouts_in_probe=0,
            velocity_at_probe_start=snap.combined_velocity,
        )
        self.self_eval_history.append(
            {
                "event": "started",
                "attempt": attempt,
                "queue": list(queue),
                "velocity": round(snap.combined_velocity, 6),
            }
        )
        if len(self.self_eval_history) > 20:
            self.self_eval_history = self.self_eval_history[-20:]
        return True

    def _plan_for_recovery_strategy(
        self,
        strategy: str,
        snap: LearningSnapshot,
        *,
        for_probe: bool = False,
    ) -> MetaActionPlan:
        primary = _recovery_from_str(strategy)
        mine = False
        mine_aggressive = False
        expand_data = False
        escalation_delta = 0
        explore_mult = self.explore_multiplier
        intra_delta: float | None = None
        reward_tweak: BirthRewardConfig | None = None
        rationale = f"self_eval_{strategy}"

        if primary == RecoveryStrategy.PATTERN_INJECT_AGGRESSIVE:
            mine = True
            mine_aggressive = True
            rationale = "self_eval_pattern_inject_aggressive"
        elif primary == RecoveryStrategy.EXPLORE_BOOST:
            escalation_delta = 1
            explore_mult = 1.0
            rationale = "self_eval_explore_boost"
        elif primary == RecoveryStrategy.REWARD_SHAPING_TWEAK:
            reward_tweak = self._apply_reward_tweak(snap)
            if reward_tweak is None and snap.volume_gate_passed:
                step = float(self.cfg.meta_reward_tweak_step)
                cap = float(self.cfg.meta_max_expectancy_coeff)
                new_coeff = min(cap, self.active_reward.expectancy_coeff + step)
                if new_coeff > self.active_reward.expectancy_coeff:
                    self.active_reward = replace(
                        self.active_reward, expectancy_coeff=new_coeff
                    )
                    reward_tweak = replace(self.active_reward)
            rationale = "self_eval_reward_shaping_tweak"
        elif primary == RecoveryStrategy.DATA_EXPANSION:
            expand_data = True
            rationale = "self_eval_data_expansion"
        elif primary == RecoveryStrategy.INTRA_EASE:
            intra_delta = -float(self.cfg.intra_hard_pct_step)
            rationale = "self_eval_intra_ease"
        elif primary == RecoveryStrategy.EXPLORE_REDUCE:
            explore_mult = max(
                0.4,
                min(1.0, float(self.cfg.meta_explore_decay_stall)),
            )
            rationale = "self_eval_explore_reduce"

        if for_probe and primary == RecoveryStrategy.EXPLORE_REDUCE:
            explore_mult = max(0.4, min(1.0, float(self.cfg.meta_explore_decay_stall)))

        return MetaActionPlan(
            primary=primary,
            escalation_delta=escalation_delta,
            mine=mine,
            mine_aggressive=mine_aggressive,
            expand_data=expand_data,
            reward_tweak=reward_tweak,
            intra_hard_pct_delta=intra_delta,
            explore_steps_multiplier=explore_mult,
            rationale=rationale,
            snapshot=snap,
            self_eval_phase=self.self_eval.phase.value,
            committed_strategy=self.self_eval.committed_strategy,
        )

    def decide_probe_rollout(self, snap: LearningSnapshot) -> MetaActionPlan:
        if self.self_eval.phase != SelfEvalPhase.PROBING or not self.self_eval.current_strategy:
            return _hold_plan(snap, "self_eval_not_probing")
        plan = self._plan_for_recovery_strategy(
            self.self_eval.current_strategy,
            snap,
            for_probe=True,
        )
        self._record_plan(plan)
        return plan

    def on_probe_rollout_complete(
        self,
        snap: LearningSnapshot,
        *,
        attempt: int,
    ) -> MetaActionPlan | None:
        if self.self_eval.phase == SelfEvalPhase.COMMITTED:
            if snap.learning_health == LearningHealth.IMPROVING and snap.volume_gate_passed:
                self.self_eval = SelfEvalState(
                    cooldown_until_attempt=self.self_eval.cooldown_until_attempt,
                )
            return None

        if self.self_eval.phase == SelfEvalPhase.EXHAUSTED:
            return MetaActionPlan(
                primary=RecoveryStrategy.HOLD,
                suggest_provisional_pass=True,
                rationale="self_eval_exhausted",
                snapshot=snap,
                self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
            )

        if self.self_eval.phase != SelfEvalPhase.PROBING:
            return None

        self.self_eval.rollouts_in_probe += 1
        per_strategy = int(self.cfg.meta_self_eval_rollouts_per_strategy)
        if self.self_eval.rollouts_in_probe < per_strategy:
            return None

        completed = self.self_eval.current_strategy or ""
        delta = score_probe_result(
            velocity_start=self.self_eval.velocity_at_probe_start,
            velocity_end=snap.combined_velocity,
        )
        self.self_eval.probe_results.append(
            StrategyProbeResult(
                strategy=completed,
                rollouts=per_strategy,
                velocity_start=self.self_eval.velocity_at_probe_start,
                velocity_end=snap.combined_velocity,
                velocity_delta=delta,
                combined_at_end=snap.combined_velocity,
            )
        )
        self.self_eval_history.append(
            {
                "event": "probe_complete",
                "strategy": completed,
                "velocity_delta": round(delta, 6),
                "combined_at_end": round(snap.combined_velocity, 6),
            }
        )
        if len(self.self_eval_history) > 20:
            self.self_eval_history = self.self_eval_history[-20:]

        if self.self_eval.probe_queue and self.self_eval.probe_queue[0] == completed:
            self.self_eval.probe_queue = self.self_eval.probe_queue[1:]
        else:
            self.self_eval.probe_queue = [
                s for s in self.self_eval.probe_queue if s != completed
            ]

        if self.self_eval.probe_queue:
            self.self_eval.current_strategy = self.self_eval.probe_queue[0]
            self.self_eval.rollouts_in_probe = 0
            self.self_eval.velocity_at_probe_start = snap.combined_velocity
            return None

        winner = select_winner(self.self_eval.probe_results, self.cfg)
        if winner:
            self.self_eval.phase = SelfEvalPhase.COMMITTED
            self.self_eval.committed_strategy = winner
            self.self_eval.current_strategy = None
            self.self_eval.rollouts_in_probe = 0
            self.self_eval_history.append({"event": "committed", "strategy": winner})
            return self._plan_for_recovery_strategy(winner, snap)

        self.self_eval.phase = SelfEvalPhase.EXHAUSTED
        self.self_eval.pending_provisional = True
        self.self_eval.cooldown_until_attempt = attempt + int(
            self.cfg.meta_self_eval_cooldown_rollouts
        )
        self.self_eval.current_strategy = None
        self.self_eval_history.append({"event": "exhausted"})
        return MetaActionPlan(
            primary=RecoveryStrategy.HOLD,
            suggest_provisional_pass=True,
            rationale="self_eval_no_winner",
            snapshot=snap,
            self_eval_phase=SelfEvalPhase.EXHAUSTED.value,
        )

    def decide_committed_rollout(self, snap: LearningSnapshot) -> MetaActionPlan:
        if (
            self.self_eval.phase != SelfEvalPhase.COMMITTED
            or not self.self_eval.committed_strategy
        ):
            return _hold_plan(snap, "self_eval_not_committed")
        plan = self._plan_for_recovery_strategy(
            self.self_eval.committed_strategy,
            snap,
        )
        plan = MetaActionPlan(
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
            explore_steps_multiplier=plan.explore_steps_multiplier,
            rationale=plan.rationale,
            snapshot=snap,
            self_eval_phase=SelfEvalPhase.COMMITTED.value,
            committed_strategy=self.self_eval.committed_strategy,
        )
        self._record_plan(plan)
        return plan

    def evaluate_provisional_fallback(
        self,
        snap: LearningSnapshot,
        *,
        allow_provisional: bool,
        strong_recovery_attempts: int,
        stage_trades: int,
        required: int,
        attempt: int,
        patterns_mined: int,
        buffer_size: int,
        constitution_violations: int,
    ) -> ProvisionalFallbackResult:
        exhausted = self.self_eval.phase == SelfEvalPhase.EXHAUSTED
        if not exhausted and not self.self_eval.pending_provisional:
            return ProvisionalFallbackResult(
                should_grant=False,
                reason="",
                blocked_reason="self_eval_not_exhausted",
                safeguards={"self_eval_exhausted": False},
            )

        from lumina_core.birth.curriculum import should_gen0_soft_pass

        soft_pass_eligible = should_gen0_soft_pass(
            stage_trades=stage_trades,
            buffer_size=buffer_size,
            attempt=attempt,
            cfg=self.cfg,
        ) or (patterns_mined >= 100 and buffer_size >= 256)
        recovery_met = (
            strong_recovery_attempts >= self.cfg.strong_recovery_no_improvement_threshold
            or exhausted
        )
        safeguards = {
            "allow_provisional": allow_provisional,
            "constitution_clean": constitution_violations == 0,
            "volume_gate_passed": stage_trades >= required,
            "recovery_attempts_met": recovery_met,
            "velocity_still_low": snap.combined_velocity <= self.cfg.velocity_stall_epsilon,
            "soft_pass_eligible": soft_pass_eligible,
            "self_eval_exhausted": exhausted,
        }
        if not allow_provisional:
            return ProvisionalFallbackResult(
                should_grant=False,
                reason="",
                blocked_reason="certified_mode_strict",
                safeguards=safeguards,
            )
        if all(
            (
                safeguards["constitution_clean"],
                safeguards["volume_gate_passed"],
                safeguards["recovery_attempts_met"],
                safeguards["velocity_still_low"],
                safeguards["soft_pass_eligible"],
                safeguards["self_eval_exhausted"],
            )
        ):
            return ProvisionalFallbackResult(
                should_grant=True,
                reason="self_eval_exhausted_soft_pass",
                blocked_reason=None,
                safeguards=safeguards,
            )
        blocked_reason = next(
            (
                key
                for key, ok in (
                    ("constitution_clean", safeguards["constitution_clean"]),
                    ("volume_gate_passed", safeguards["volume_gate_passed"]),
                    ("recovery_attempts_met", safeguards["recovery_attempts_met"]),
                    ("velocity_still_low", safeguards["velocity_still_low"]),
                    ("soft_pass_eligible", safeguards["soft_pass_eligible"]),
                    ("self_eval_exhausted", safeguards["self_eval_exhausted"]),
                )
                if not ok
            ),
            "safeguard_failed",
        )
        return ProvisionalFallbackResult(
            should_grant=False,
            reason="",
            blocked_reason=blocked_reason,
            safeguards=safeguards,
        )

    def format_self_eval_suffix(self) -> str:
        se = self.self_eval
        if se.phase == SelfEvalPhase.IDLE:
            return ""
        per = int(self.cfg.meta_self_eval_rollouts_per_strategy)
        if se.phase == SelfEvalPhase.PROBING and se.current_strategy:
            delta = 0.0
            if se.probe_results:
                delta = se.probe_results[-1].velocity_delta
            return (
                f" · self-eval: probing {se.current_strategy} "
                f"({se.rollouts_in_probe}/{per}) · velocity Δ={delta:+.4f}"
            )
        if se.phase == SelfEvalPhase.COMMITTED and se.committed_strategy:
            return f" · self-eval: committed {se.committed_strategy}"
        if se.phase == SelfEvalPhase.EXHAUSTED:
            return " · self-eval: exhausted (provisional considered)"
        return ""

    def _record_plan(self, plan: MetaActionPlan) -> None:
        entry = {
            "primary": plan.primary.value,
            "secondary": [s.value for s in plan.secondary],
            "rationale": plan.rationale,
        }
        self.strategy_history.append(entry)
        if len(self.strategy_history) > 50:
            self.strategy_history = self.strategy_history[-50:]
