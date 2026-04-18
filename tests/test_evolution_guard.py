from __future__ import annotations

from datetime import datetime, timedelta, timezone

from lumina_core.evolution.evolution_guard import EvolutionGuard


def test_can_mutate_only_in_sim_and_paper() -> None:
    guard = EvolutionGuard()

    assert guard.can_mutate(mode="sim") is True
    assert guard.can_mutate(mode="paper") is True
    assert guard.can_mutate(mode="real") is False


def test_signed_approval_requires_confidence_and_better_fitness() -> None:
    guard = EvolutionGuard(confidence_threshold=0.85)

    assert guard.has_signed_approval(confidence=0.9, candidate_fitness=2.0, current_fitness=1.0) is True
    assert guard.has_signed_approval(confidence=0.84, candidate_fitness=2.0, current_fitness=1.0) is False
    assert guard.has_signed_approval(confidence=0.9, candidate_fitness=1.0, current_fitness=1.0) is False


def test_rollback_triggers_for_worse_candidate_within_window() -> None:
    guard = EvolutionGuard()
    now = datetime.now(timezone.utc)
    promoted_at = now - timedelta(minutes=30)

    assert (
        guard.should_rollback(
            promoted_at=promoted_at,
            candidate_fitness=0.4,
            previous_fitness=0.8,
            now=now,
        )
        is True
    )
    assert (
        guard.should_rollback(
            promoted_at=now - timedelta(hours=2),
            candidate_fitness=0.4,
            previous_fitness=0.8,
            now=now,
        )
        is False
    )
