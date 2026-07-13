"""Self-adaptive window and rollout parameter tuning for birth recovery."""

from __future__ import annotations

from dataclasses import dataclass, field

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.meta_controller import LearningHealth


@dataclass(frozen=True, slots=True)
class AdaptiveParameterPatch:
    winrate_trend_window: int | None = None
    reward_trend_window: int | None = None
    chunk_target: int | None = None
    expand_data: bool = False
    rationale: str = ""


def _clamp_window(value: int, *, default: int, minimum: int = 5, maximum: int = 24) -> int:
    return max(minimum, min(maximum, value))


def compute_parameter_patch(
    *,
    learning_health: LearningHealth | str,
    current_winrate_window: int,
    current_reward_window: int,
    cfg: BirthCurriculumConfig,
    adaptation_tier: int = 0,
    post_volume_gate: bool = False,
) -> AdaptiveParameterPatch:
    """Bounded tuning after rollout observation."""
    default_wr = int(cfg.winrate_trend_window)
    default_rw = int(cfg.reward_trend_window)
    health = (
        learning_health
        if isinstance(learning_health, LearningHealth)
        else LearningHealth(str(learning_health))
    )

    wr_window: int | None = None
    rw_window: int | None = None
    rationale_parts: list[str] = []

    if health in {LearningHealth.DECLINING, LearningHealth.FLAT}:
        wr_window = _clamp_window(current_winrate_window + 2, default=default_wr)
        rw_window = _clamp_window(current_reward_window + 2, default=default_rw)
        rationale_parts.append(f"widen_windows_health={health.value}")
    elif health == LearningHealth.IMPROVING:
        if current_winrate_window > default_wr:
            wr_window = _clamp_window(current_winrate_window - 1, default=default_wr)
            rationale_parts.append("narrow_winrate_window")
        if current_reward_window > default_rw:
            rw_window = _clamp_window(current_reward_window - 1, default=default_rw)
            rationale_parts.append("narrow_reward_window")

    chunk_target: int | None = None
    if post_volume_gate and health == LearningHealth.DECLINING:
        chunk_target = min(25, cfg.exploration_chunk_size * 2)
        rationale_parts.append("boost_chunk_declining")

    expand_data = adaptation_tier >= 2 and bool(cfg.auto_expand_on_adaptation)

    if not rationale_parts and not expand_data:
        return AdaptiveParameterPatch()

    return AdaptiveParameterPatch(
        winrate_trend_window=wr_window,
        reward_trend_window=rw_window,
        chunk_target=chunk_target,
        expand_data=expand_data,
        rationale="; ".join(rationale_parts) or "tier_expand",
    )


@dataclass(slots=True)
class WallAdaptationState:
    """Handler-owned adaptation counters and history."""

    adaptation_tier: int = 0
    retries_this_stage: int = 0
    escalation_level: int = 0
    adaptation_history: list[dict] = field(default_factory=list)
    wall_triggers_total: int = 0
    recovery_attempts: int = 0
    recovery_successes: int = 0
    last_adaptation_stage_trades: int = 0
    adaptation_stuck_escapes: int = 0
    effective_winrate_window: int = 12
    effective_reward_window: int = 12

    @property
    def autonomous_recovery_rate_pct(self) -> float:
        if self.recovery_attempts <= 0:
            return 0.0
        return round(
            (float(self.recovery_successes) / float(self.recovery_attempts)) * 100.0,
            2,
        )

    def to_metrics(self) -> dict[str, object]:
        return {
            "adaptation_tier": int(self.adaptation_tier),
            "retries_this_stage": int(self.retries_this_stage),
            "escalation_level": int(self.escalation_level),
            "adaptation_history": list(self.adaptation_history[-20:]),
            "wall_triggers_total": int(self.wall_triggers_total),
            "autonomous_recovery_attempts": int(self.recovery_attempts),
            "autonomous_recovery_successes": int(self.recovery_successes),
            "autonomous_recovery_rate_pct": self.autonomous_recovery_rate_pct,
            "last_adaptation_stage_trades": int(self.last_adaptation_stage_trades),
            "adaptation_stuck_escapes": int(self.adaptation_stuck_escapes),
            "effective_winrate_trend_window": int(self.effective_winrate_window),
            "effective_reward_trend_window": int(self.effective_reward_window),
        }

    @classmethod
    def from_metrics(cls, metrics: dict | None, *, cfg: BirthCurriculumConfig) -> WallAdaptationState:
        if not isinstance(metrics, dict):
            return cls(
                effective_winrate_window=int(cfg.winrate_trend_window),
                effective_reward_window=int(cfg.reward_trend_window),
            )
        history = metrics.get("adaptation_history")
        return cls(
            adaptation_tier=int(metrics.get("adaptation_tier", 0) or 0),
            retries_this_stage=int(metrics.get("retries_this_stage", 0) or 0),
            escalation_level=int(metrics.get("escalation_level", 0) or 0),
            adaptation_history=[
                dict(x) for x in history if isinstance(x, dict)
            ]
            if isinstance(history, list)
            else [],
            wall_triggers_total=int(metrics.get("wall_triggers_total", 0) or 0),
            recovery_attempts=int(metrics.get("autonomous_recovery_attempts", 0) or 0),
            recovery_successes=int(metrics.get("autonomous_recovery_successes", 0) or 0),
            last_adaptation_stage_trades=int(
                metrics.get("last_adaptation_stage_trades", 0) or 0
            ),
            adaptation_stuck_escapes=int(
                metrics.get("adaptation_stuck_escapes", 0) or 0
            ),
            effective_winrate_window=int(
                metrics.get(
                    "effective_winrate_trend_window",
                    metrics.get("winrate_trend_window", cfg.winrate_trend_window),
                )
                or cfg.winrate_trend_window
            ),
            effective_reward_window=int(
                metrics.get(
                    "effective_reward_trend_window",
                    metrics.get("reward_trend_window", cfg.reward_trend_window),
                )
                or cfg.reward_trend_window
            ),
        )


__all__ = [
    "AdaptiveParameterPatch",
    "WallAdaptationState",
    "compute_parameter_patch",
]
