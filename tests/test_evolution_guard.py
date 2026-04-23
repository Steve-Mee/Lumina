from __future__ import annotations

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any

from lumina_core.evolution.evolution_guard import EvolutionGuard


@dataclass
class _MockSimResult:
    dna_hash: str = "test"
    day_count: int = 3
    avg_pnl: float = 500.0
    max_drawdown_ratio: float = 0.01
    regime_fit_bonus: float = 0.0
    fitness: float = 1.5
    shadow_mode: bool = True
    hypothetical_fills: list = None  # type: ignore[assignment]


class _MockShadowRunner:
    """Minimal shadow runner that returns a passing SimResult."""

    def evaluate_variants(self, variants: list, *, days: int, shadow_mode: bool = False, **_: Any) -> list:
        return [_MockSimResult(dna_hash=getattr(v, "hash", "test")) for v in variants]


class _MockTwin:
    """Minimal approval twin that always approves."""

    def evaluate_dna_promotion(self, _dna: Any) -> dict:
        return {"recommendation": True, "confidence": 0.95}


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
    shadow_runner = _MockShadowRunner()
    twin = _MockTwin()
    dna = type("DNA", (), {"hash": "abc123"})()

    assert guard.requires_approval_twin(mode="real") is True
    # Without shadow_runner, dna, approval_twin – must return False in REAL mode
    assert (
        guard.has_signed_approval(
            mode="real",
            confidence=0.95,
            candidate_fitness=2.5,
            current_fitness=1.0,
            approval_twin_recommendation=None,
        )
        is False
    )
    # With full shadow wiring and recommendation=True – shadow passes, returns True
    assert (
        guard.has_signed_approval(
            mode="real",
            confidence=0.97,
            candidate_fitness=2.5,
            current_fitness=1.0,
            approval_twin_recommendation=True,
            approval_twin=twin,
            dna=dna,
            shadow_runner=shadow_runner,
        )
        is True
    )


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

        def evaluate_dna_promotion(self, _dna: Any) -> dict:
            self.calls += 1
            return {"recommendation": True, "confidence": 0.97}

    guard = EvolutionGuard(confidence_threshold=0.85)
    twin = _Twin()
    shadow_runner = _MockShadowRunner()
    dna = type("DNA", (), {"hash": "xyz"})()

    result = guard.has_signed_approval(
        mode="real",
        confidence=0.97,
        candidate_fitness=2.5,
        current_fitness=1.0,
        approval_twin_recommendation=None,
        approval_twin=twin,
        dna=dna,
        shadow_runner=shadow_runner,
    )

    assert result is True
    assert twin.calls == 1


def test_real_mode_signed_approval_blocks_below_zero_touch_twin_floor() -> None:
    guard = EvolutionGuard()
    twin = _MockTwin()
    shadow_runner = _MockShadowRunner()
    dna = type("DNA", (), {"hash": "lowconf"})()

    assert (
        guard.has_signed_approval(
            mode="real",
            confidence=0.96,
            candidate_fitness=2.5,
            current_fitness=1.0,
            approval_twin_recommendation=True,
            approval_twin=twin,
            dna=dna,
            shadow_runner=shadow_runner,
        )
        is False
    )


def test_real_mode_signed_approval_blocks_non_empty_twin_risk_flags() -> None:
    class _TwinFlags:
        def evaluate_dna_promotion(self, _dna: Any) -> dict:
            return {"recommendation": True, "confidence": 0.99, "risk_flags": ["SIZE"]}

    guard = EvolutionGuard()
    twin = _TwinFlags()
    shadow_runner = _MockShadowRunner()
    dna = type("DNA", (), {"hash": "flags"})()

    assert (
        guard.has_signed_approval(
            mode="real",
            confidence=0.99,
            candidate_fitness=2.5,
            current_fitness=1.0,
            approval_twin_recommendation=True,
            approval_twin=twin,
            dna=dna,
            shadow_runner=shadow_runner,
            twin_risk_flags=["SIZE"],
        )
        is False
    )


def test_is_confidence_gated_promotion_requires_0_97_and_clean_flags() -> None:
    guard = EvolutionGuard()
    dna = type("DNA", (), {"fitness_score": 1.0})()

    ok = guard.is_confidence_gated_promotion(
        dna,
        0.97,
        True,
        2.0,
        previous_fitness=1.0,
        twin_risk_flags=[],
    )
    blocked_conf = guard.is_confidence_gated_promotion(
        dna,
        0.96,
        True,
        2.0,
        previous_fitness=1.0,
        twin_risk_flags=[],
    )
    blocked_flags = guard.is_confidence_gated_promotion(
        dna,
        0.98,
        True,
        2.0,
        previous_fitness=1.0,
        twin_risk_flags=["X"],
    )

    assert ok is True
    assert blocked_conf is False
    assert blocked_flags is False


def test_evaluate_passes_twin_risk_flags_to_has_signed_approval() -> None:
    guard = EvolutionGuard()
    twin = _MockTwin()
    shadow_runner = _MockShadowRunner()
    dna = type("DNA", (), {"hash": "e1"})()
    d = guard.evaluate(
        mode="real",
        confidence=0.97,
        candidate_fitness=2.0,
        previous_fitness=1.0,
        approval_twin_recommendation=True,
        approval_twin=twin,
        dna=dna,
        shadow_runner=shadow_runner,
        twin_risk_flags=["RISK"],
    )
    assert d.signed_approval is False


def test_should_rollback_respects_extended_window() -> None:
    guard = EvolutionGuard()
    now = datetime.now(timezone.utc)
    promoted_at = now - timedelta(hours=12)

    assert (
        guard.should_rollback(
            promoted_at=promoted_at,
            candidate_fitness=0.2,
            previous_fitness=0.9,
            now=now,
            window=timedelta(hours=24),
        )
        is True
    )
    assert (
        guard.should_rollback(
            promoted_at=promoted_at,
            candidate_fitness=0.2,
            previous_fitness=0.9,
            now=now,
            window=timedelta(hours=1),
        )
        is False
    )


def test_allows_neuroevolution_winner_requires_confidence_and_improvement() -> None:
    guard = EvolutionGuard(confidence_threshold=0.85)

    assert (
        guard.allows_neuroevolution_winner(
            candidate_confidence=0.92,
            candidate_fitness=1.20,
            current_fitness=1.10,
            min_improvement=0.05,
        )
        is True
    )
    assert (
        guard.allows_neuroevolution_winner(
            candidate_confidence=0.80,
            candidate_fitness=1.25,
            current_fitness=1.10,
            min_improvement=0.05,
        )
        is False
    )
    assert (
        guard.allows_neuroevolution_winner(
            candidate_confidence=0.92,
            candidate_fitness=1.12,
            current_fitness=1.10,
            min_improvement=0.05,
        )
        is False
    )


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


def test_generated_strategy_gate_requires_higher_confidence() -> None:
    guard = EvolutionGuard(confidence_threshold=0.85)

    allowed = guard.allows_generated_strategy(
        candidate_confidence=0.91,
        candidate_fitness=1.6,
        current_fitness=1.0,
        min_backtest_fitness=1.3,
        min_improvement=0.2,
    )
    blocked = guard.allows_generated_strategy(
        candidate_confidence=0.89,
        candidate_fitness=2.0,
        current_fitness=1.0,
        min_backtest_fitness=1.3,
        min_improvement=0.2,
    )

    assert allowed is True
    assert blocked is False


def test_generated_strategy_gate_requires_backtest_threshold_or_lift() -> None:
    guard = EvolutionGuard(confidence_threshold=0.80)

    blocked = guard.allows_generated_strategy(
        candidate_confidence=0.95,
        candidate_fitness=1.05,
        current_fitness=1.0,
        min_backtest_fitness=1.2,
        min_improvement=0.1,
    )
    allowed = guard.allows_generated_strategy(
        candidate_confidence=0.95,
        candidate_fitness=1.25,
        current_fitness=1.0,
        min_backtest_fitness=1.2,
        min_improvement=0.1,
    )

    assert blocked is False
    assert allowed is True


def test_generated_strategy_survival_requires_shadow_pass() -> None:
    guard = EvolutionGuard(confidence_threshold=0.80)

    blocked = guard.generated_strategy_survives(
        mode="sim",
        candidate_confidence=0.95,
        candidate_fitness=1.3,
        current_fitness=1.0,
        shadow_total_pnl=0.0,
        approval_twin_recommendation=True,
        min_backtest_fitness=1.2,
        min_improvement=0.1,
    )
    allowed = guard.generated_strategy_survives(
        mode="sim",
        candidate_confidence=0.95,
        candidate_fitness=1.3,
        current_fitness=1.0,
        shadow_total_pnl=10.0,
        approval_twin_recommendation=True,
        min_backtest_fitness=1.2,
        min_improvement=0.1,
    )

    assert blocked is False
    assert allowed is True


def test_generated_strategy_survival_requires_twin_in_real_mode() -> None:
    guard = EvolutionGuard(confidence_threshold=0.80)

    blocked = guard.generated_strategy_survives(
        mode="real",
        candidate_confidence=0.95,
        candidate_fitness=1.4,
        current_fitness=1.0,
        shadow_total_pnl=5.0,
        approval_twin_recommendation=False,
        min_backtest_fitness=1.2,
        min_improvement=0.1,
    )
    allowed = guard.generated_strategy_survives(
        mode="real",
        candidate_confidence=0.95,
        candidate_fitness=1.4,
        current_fitness=1.0,
        shadow_total_pnl=5.0,
        approval_twin_recommendation=True,
        min_backtest_fitness=1.2,
        min_improvement=0.1,
    )

    assert blocked is False
    assert allowed is True
