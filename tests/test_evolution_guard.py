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


def test_real_mode_requires_approval_twin_recommendation() -> None:
    guard = EvolutionGuard(confidence_threshold=0.85)

    assert guard.requires_approval_twin(mode="real") is True
    assert guard.has_signed_approval(
        mode="real",
        confidence=0.95,
        candidate_fitness=2.5,
        current_fitness=1.0,
        approval_twin_recommendation=None,
    ) is False
    assert guard.has_signed_approval(
        mode="real",
        confidence=0.95,
        candidate_fitness=2.5,
        current_fitness=1.0,
        approval_twin_recommendation=True,
    ) is True


def test_resolve_approval_twin_recommendation_from_agent_dict() -> None:
    class _Twin:
        def evaluate_dna_promotion(self, _dna):
            return {"recommendation": True, "confidence": 0.93}

    guard = EvolutionGuard()

    assert guard.resolve_approval_twin_recommendation(approval_twin=_Twin(), dna={"hash": "abc"}) is True
    assert guard.resolve_approval_twin_recommendation(approval_twin=None, dna={"hash": "abc"}) is False


def test_real_mode_signed_approval_consults_twin_when_recommendation_missing() -> None:
    class _Twin:
        def __init__(self) -> None:
            self.calls = 0

        def evaluate_dna_promotion(self, _dna):
            self.calls += 1
            return {"recommendation": True, "confidence": 0.97}

    guard = EvolutionGuard(confidence_threshold=0.85)
    twin = _Twin()

    result = guard.has_signed_approval(
        mode="real",
        confidence=0.95,
        candidate_fitness=2.5,
        current_fitness=1.0,
        approval_twin_recommendation=None,
        approval_twin=twin,
        dna={"hash": "xyz"},
    )

    assert result is True
    assert twin.calls == 1


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
