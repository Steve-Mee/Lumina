from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


def _normalize_mode(mode: str | None) -> str:
    value = str(mode or "real").strip().lower()
    return value if value in {"real", "paper", "sim"} else "real"


def _normalize_confidence(confidence: float) -> float:
    value = float(confidence or 0.0)
    if value > 1.0:
        value /= 100.0
    return max(0.0, min(1.0, value))


@dataclass(frozen=True, slots=True)
class EvolutionGuardDecision:
    mutation_allowed: bool
    signed_approval: bool
    rollback_required: bool
    revert_to_hash: str | None


@dataclass(slots=True)
class EvolutionGuard:
    confidence_threshold: float = 0.85
    rollback_window: timedelta = timedelta(hours=1)

    def can_mutate(self, *, mode: str) -> bool:
        return _normalize_mode(mode) in {"paper", "sim"}

    def has_signed_approval(
        self,
        *,
        confidence: float,
        candidate_fitness: float,
        current_fitness: float,
    ) -> bool:
        normalized_confidence = _normalize_confidence(confidence)
        return bool(
            normalized_confidence > float(self.confidence_threshold)
            and float(candidate_fitness) > float(current_fitness)
        )

    def allows_generation_progress(
        self,
        *,
        candidate_fitness: float,
        previous_generation_fitness: float,
    ) -> bool:
        return float(candidate_fitness) >= float(previous_generation_fitness)

    def should_rollback(
        self,
        *,
        promoted_at: datetime | None,
        candidate_fitness: float,
        previous_fitness: float,
        now: datetime | None = None,
    ) -> bool:
        if promoted_at is None:
            return False
        current_time = now or datetime.now(timezone.utc)
        if promoted_at.tzinfo is None:
            promoted_at = promoted_at.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        within_window = (current_time - promoted_at) <= self.rollback_window
        return bool(within_window and float(candidate_fitness) < float(previous_fitness))

    def evaluate(
        self,
        *,
        mode: str,
        confidence: float,
        candidate_fitness: float,
        previous_fitness: float,
        current_hash: str | None = None,
        promoted_at: datetime | None = None,
        now: datetime | None = None,
    ) -> EvolutionGuardDecision:
        mutation_allowed = self.can_mutate(mode=mode)
        signed_approval = self.has_signed_approval(
            confidence=confidence,
            candidate_fitness=candidate_fitness,
            current_fitness=previous_fitness,
        )
        rollback_required = self.should_rollback(
            promoted_at=promoted_at,
            candidate_fitness=candidate_fitness,
            previous_fitness=previous_fitness,
            now=now,
        )
        return EvolutionGuardDecision(
            mutation_allowed=mutation_allowed,
            signed_approval=signed_approval,
            rollback_required=rollback_required,
            revert_to_hash=str(current_hash) if rollback_required and current_hash else None,
        )