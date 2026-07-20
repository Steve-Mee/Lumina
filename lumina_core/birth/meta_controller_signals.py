"""Pure stall/adaptation signal helpers for birth meta-controller."""
from __future__ import annotations

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.meta_controller_types import (
    AdaptationDecision,
    LearningHealth,
    LearningSnapshot,
    MetaActionPlan,
    RecoveryStrategy,
    StallDetectionResult,
)
from lumina_core.birth.stage_scorecard import calculate_simple_slope, combined_learning_velocity


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
