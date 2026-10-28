"""Death-spiral circuit breaker for autonomous birth recovery (Organism Autonomy Engine)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.death_spiral_guard")

SPIRAL_SIGNATURE_FIELDS = ("curriculum_stage", "blocker_metric", "blocker_value_bucket")


def _bucket_metric(value: float, *, precision: int = 2) -> str:
    try:
        return f"{round(float(value), precision):.{precision}f}"
    except (TypeError, ValueError):
        return "0.00"


@dataclass(slots=True)
class DeathSpiralState:
    """Tracks repeated stall signatures to force novelty instead of tighter retries."""

    repeat_count: int = 0
    last_signature: str = ""
    last_signature_at: float = 0.0
    circuit_breaker_tripped: bool = False
    novelty_budget: int = 3
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_metrics(self) -> dict[str, Any]:
        return {
            "death_spiral_repeat_count": int(self.repeat_count),
            "death_spiral_last_signature": str(self.last_signature),
            "death_spiral_circuit_breaker": bool(self.circuit_breaker_tripped),
            "death_spiral_novelty_budget": int(self.novelty_budget),
            "death_spiral_history": list(self.history)[-12:],
        }

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any] | None) -> DeathSpiralState:
        if not isinstance(metrics, dict):
            return cls()
        history = metrics.get("death_spiral_history")
        return cls(
            repeat_count=int(metrics.get("death_spiral_repeat_count", 0) or 0),
            last_signature=str(metrics.get("death_spiral_last_signature", "") or ""),
            circuit_breaker_tripped=bool(metrics.get("death_spiral_circuit_breaker", False)),
            novelty_budget=max(0, int(metrics.get("death_spiral_novelty_budget", 3) or 3)),
            history=[dict(x) for x in history if isinstance(x, dict)]
            if isinstance(history, list)
            else [],
        )


def build_stall_signature(
    *,
    curriculum_stage: str,
    blocker_metric: str,
    blocker_value: float,
) -> str:
    stage = str(curriculum_stage or "unknown").strip().lower()
    metric = str(blocker_metric or "unknown").strip().lower()
    bucket = _bucket_metric(blocker_value)
    return f"{stage}|{metric}|{bucket}"


def record_stall_signature(
    state: DeathSpiralState,
    *,
    curriculum_stage: str,
    blocker_metric: str,
    blocker_value: float,
    cfg: BirthCurriculumConfig,
) -> bool:
    """Record stall and return True when circuit breaker should force novelty."""
    signature = build_stall_signature(
        curriculum_stage=curriculum_stage,
        blocker_metric=blocker_metric,
        blocker_value=blocker_value,
    )
    threshold = max(2, int(cfg.death_spiral_repeat_threshold))
    now = time.time()
    if signature == state.last_signature:
        state.repeat_count += 1
    else:
        state.repeat_count = 1
        state.last_signature = signature
        state.circuit_breaker_tripped = False
    state.last_signature_at = now
    state.history.append(
        {
            "timestamp": now,
            "signature": signature,
            "repeat_count": int(state.repeat_count),
        }
    )
    if state.repeat_count >= threshold:
        state.circuit_breaker_tripped = True
        logger.warning(
            "birth.death_spiral.circuit_breaker signature=%s repeats=%s",
            signature,
            state.repeat_count,
        )
    return state.circuit_breaker_tripped


def consume_novelty_budget(state: DeathSpiralState) -> bool:
    """Consume one novelty token; return False when budget exhausted."""
    if state.novelty_budget <= 0:
        return False
    state.novelty_budget -= 1
    return True


def reset_after_novelty(state: DeathSpiralState, *, cfg: BirthCurriculumConfig) -> None:
    state.repeat_count = 0
    state.circuit_breaker_tripped = False
    state.novelty_budget = max(1, int(cfg.death_spiral_novelty_budget))


def should_widen_data_horizon(state: DeathSpiralState, *, phoenix_count: int, cfg: BirthCurriculumConfig) -> bool:
    return (
        state.circuit_breaker_tripped
        and phoenix_count >= max(2, int(cfg.phoenix_widen_data_after_cycles))
        and state.novelty_budget <= 0
    )