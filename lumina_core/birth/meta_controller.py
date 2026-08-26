"""Birth meta-controller (learning signals + recovery strategy).

Thin façade: types and pure signals re-exported; decisions/self-eval live in mixins.
Heavy recovery is orchestrated via BirthBusClient handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage
from lumina_core.birth.meta_controller_decisions import MetaControllerDecisionsMixin
from lumina_core.birth.meta_controller_self_eval_ops import MetaControllerSelfEvalMixin
from lumina_core.birth.meta_controller_signals import (
    _classify_learning_health,
    _pattern_quality,
    detect_stall,
    get_adaptation_decision,
)
from lumina_core.birth.meta_controller_types import (
    AdaptationDecision,
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
)
from lumina_core.birth.meta_self_eval import SelfEvalState

# Re-export public surface (import stability for engine/bus/tests)
__all__ = [
    "AdaptationDecision",
    "BirthMetaController",
    "LearningHealth",
    "LearningSnapshot",
    "MetaActionPlan",
    "RecoveryStrategy",
    "StallDetectionResult",
    "detect_stall",
    "get_adaptation_decision",
]


@dataclass(slots=True)
class BirthMetaController(MetaControllerDecisionsMixin, MetaControllerSelfEvalMixin):
    """Observe birth learning signals and recommend recovery / curriculum adjustments.

    approval_twin (optional): ApprovalTwinAgent used as primary auto-approval signal
    for evolution steps / policy candidates during birth. Calls are best-effort and
    emit to EventBus.
    """

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
    approval_twin: Any | None = field(default=None)

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
        constitution_violations: int = 0,
        range_total_signals: int = 0,
        plateau_active: bool = False,
        expectancy_quality_step: int = 0,
        stage_wins: int = 0,
        rolling_winrate: float | None = None,
        volume_gate_passed: bool | None = None,
        edge_vs_random: float | None = None,
        median_loss_r: float | None = None,
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
        gate_passed = (
            bool(volume_gate_passed)
            if volume_gate_passed is not None
            else stage_trades >= required_trades
        )
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
            volume_gate_passed=gate_passed,
            range_flat_ratio=float(range_flat_ratio),
            range_round_trips=int(range_round_trips),
            constitution_violations=max(0, int(constitution_violations)),
            range_total_signals=max(0, int(range_total_signals)),
            plateau_active=bool(plateau_active),
            expectancy_quality_step=max(0, int(expectancy_quality_step)),
            stage_wins=max(0, int(stage_wins)),
            rolling_winrate=(
                float(rolling_winrate) if rolling_winrate is not None else None
            ),
            edge_vs_random=(
                float(edge_vs_random) if edge_vs_random is not None else None
            ),
            median_loss_r=(
                float(median_loss_r) if median_loss_r is not None else None
            ),
        )
        return snap, stall

    def _record_plan(self, plan: MetaActionPlan) -> None:
        entry = {
            "primary": plan.primary.value,
            "secondary": [s.value for s in plan.secondary],
            "rationale": plan.rationale,
        }
        self.strategy_history.append(entry)
        if len(self.strategy_history) > 50:
            self.strategy_history = self.strategy_history[-50:]
