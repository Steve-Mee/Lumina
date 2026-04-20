from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


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
        mode: str | None = None,
        approval_twin_recommendation: bool | None = None,
        approval_twin: Any | None = None,
        dna: Any | None = None,
        shadow_runner: Any | None = None,
    ) -> bool:
        normalized_confidence = _normalize_confidence(confidence)
        local_gate = bool(
            normalized_confidence > float(self.confidence_threshold)
            and float(candidate_fitness) > float(current_fitness)
        )

        if mode is None or _normalize_mode(mode) != "real":
            return local_gate

        # Shadow flow voor REAL – alle drie vereist
        if approval_twin is None or dna is None or shadow_runner is None:
            return False

        recommendation = approval_twin_recommendation
        if recommendation is None:
            try:
                result = approval_twin.evaluate_dna_promotion(dna)
                recommendation = bool(result.get("recommendation", False) if isinstance(result, dict) else False)
            except Exception:
                recommendation = False

        if not recommendation:
            return False

        # Start shadow run
        shadow_days = self.resolve_shadow_days()
        try:
            shadow_results = shadow_runner.evaluate_variants(
                variants=[dna],
                days=shadow_days,
                shadow_mode=True,
            )
        except Exception:
            return False

        if not shadow_results:
            return False

        shadow_result = shadow_results[0]
        veto_blocked = False  # wordt later gevuld via Telegram reply in orchestrator

        return self.shadow_validation_passed(
            shadow_total_pnl=float(shadow_result.avg_pnl),
            veto_blocked=veto_blocked,
            risk_flags=list(getattr(shadow_result, "risk_flags", []) or []),
        )

    def requires_approval_twin(self, *, mode: str) -> bool:
        return _normalize_mode(mode) == "real"

    def resolve_approval_twin_recommendation(self, *, approval_twin: Any | None, dna: Any) -> bool:
        if approval_twin is None or dna is None or not hasattr(approval_twin, "evaluate_dna_promotion"):
            return False
        try:
            result = approval_twin.evaluate_dna_promotion(dna)
        except Exception:
            return False
        if isinstance(result, dict):
            return bool(result.get("recommendation", False))
        return False

    def should_trigger_telegram(
        self,
        *,
        twin_confidence: float,
        risk_flags: list,
    ) -> bool:
        """Return True when twin is highly confident with no risk flags.

        Kept for compatibility: confidence > 90% AND no risk_flags.
        """
        return _normalize_confidence(twin_confidence) > 0.90 and len(list(risk_flags)) == 0

    def resolve_shadow_days(self, *, minimum_days: int = 3, maximum_days: int = 7) -> int:
        low = max(1, int(minimum_days))
        high = max(low, int(maximum_days))
        return int(random.randint(low, high))

    def shadow_validation_passed(
        self,
        *,
        shadow_total_pnl: float,
        veto_blocked: bool,
        risk_flags: list[str] | None = None,
    ) -> bool:
        return bool(float(shadow_total_pnl) > 0.0 and not veto_blocked and len(list(risk_flags or [])) == 0)

    def is_confidence_gated_promotion(
        self,
        dna: Any,
        twin_confidence: float,
        shadow_passed: bool,
        backtest_fitness: float,
        previous_fitness: float | None = None,
    ) -> bool:
        """REAL promotion gate: twin >= 0.92 + positive shadow + backtest fitness improvement."""
        confidence_ok = _normalize_confidence(twin_confidence) >= 0.92
        if not confidence_ok or not bool(shadow_passed):
            return False

        baseline_fitness: float
        if previous_fitness is None:
            try:
                baseline_fitness = float(getattr(dna, "fitness_score", 0.0) or 0.0)
            except Exception:
                baseline_fitness = 0.0
        else:
            baseline_fitness = float(previous_fitness)

        return float(backtest_fitness) > baseline_fitness

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
        approval_twin_recommendation: bool | None = None,
        approval_twin: Any | None = None,
        dna: Any | None = None,
        shadow_runner: Any | None = None,
        current_hash: str | None = None,
        promoted_at: datetime | None = None,
        now: datetime | None = None,
    ) -> EvolutionGuardDecision:
        mutation_allowed = self.can_mutate(mode=mode)
        signed_approval = self.has_signed_approval(
            confidence=confidence,
            candidate_fitness=candidate_fitness,
            current_fitness=previous_fitness,
            mode=mode,
            approval_twin_recommendation=approval_twin_recommendation,
            approval_twin=approval_twin,
            dna=dna,
            shadow_runner=shadow_runner,
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
