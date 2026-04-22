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
    #: REAL zero-touch autonomous promotion (twin + shadow + backtest) requires this floor or higher.
    zero_touch_twin_floor: float = 0.97
    #: Rollback window after a zero-touch REAL promotion (fitness regression guard).
    autonomous_real_rollback_window: timedelta = timedelta(hours=24)

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
        twin_risk_flags: list[str] | None = None,
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

        if _normalize_confidence(confidence) < float(self.zero_touch_twin_floor):
            return False
        if len(list(twin_risk_flags or [])) > 0:
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
        twin_risk_flags: list[str] | None = None,
    ) -> bool:
        """REAL zero-touch gate: twin >= ``zero_touch_twin_floor``, clean risk flags, shadow + backtest."""
        confidence_ok = _normalize_confidence(twin_confidence) >= float(self.zero_touch_twin_floor)
        if not confidence_ok or not bool(shadow_passed):
            return False
        if len(list(twin_risk_flags or [])) > 0:
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

    def allows_generated_strategy(
        self,
        *,
        candidate_confidence: float,
        candidate_fitness: float,
        current_fitness: float,
        min_backtest_fitness: float = 0.0,
        min_improvement: float = 0.10,
    ) -> bool:
        """Extra gate for self-generated strategies: stricter confidence and backtest lift."""
        confidence = _normalize_confidence(candidate_confidence)
        required_confidence = max(float(self.confidence_threshold), 0.90)
        if confidence < required_confidence:
            return False

        baseline = float(current_fitness)
        required_fitness = max(float(min_backtest_fitness), baseline + float(min_improvement))
        return float(candidate_fitness) >= required_fitness

    def generated_strategy_survives(
        self,
        *,
        mode: str,
        candidate_confidence: float,
        candidate_fitness: float,
        current_fitness: float,
        shadow_total_pnl: float,
        shadow_risk_flags: list[str] | None = None,
        approval_twin_recommendation: bool | None = None,
        min_backtest_fitness: float = 0.0,
        min_improvement: float = 0.10,
    ) -> bool:
        """Generated strategy survival gate: fitness lift + shadow pass (+ twin in REAL)."""
        if not self.allows_generated_strategy(
            candidate_confidence=candidate_confidence,
            candidate_fitness=candidate_fitness,
            current_fitness=current_fitness,
            min_backtest_fitness=min_backtest_fitness,
            min_improvement=min_improvement,
        ):
            return False

        shadow_ok = self.shadow_validation_passed(
            shadow_total_pnl=float(shadow_total_pnl),
            veto_blocked=False,
            risk_flags=list(shadow_risk_flags or []),
        )
        if not shadow_ok:
            return False

        if _normalize_mode(mode) == "real" and not bool(approval_twin_recommendation):
            return False
        return True

    def allows_neuroevolution_winner(
        self,
        *,
        candidate_confidence: float,
        candidate_fitness: float,
        current_fitness: float,
        min_improvement: float = 0.01,
    ) -> bool:
        """Neuroevolution gate: enforce confidence and measurable fitness improvement."""
        confidence = _normalize_confidence(candidate_confidence)
        required_confidence = max(float(self.confidence_threshold), 0.88)
        if confidence < required_confidence:
            return False
        return float(candidate_fitness) >= float(current_fitness) + float(min_improvement)

    def should_rollback(
        self,
        *,
        promoted_at: datetime | None,
        candidate_fitness: float,
        previous_fitness: float,
        now: datetime | None = None,
        window: timedelta | None = None,
    ) -> bool:
        if promoted_at is None:
            return False
        current_time = now or datetime.now(timezone.utc)
        if promoted_at.tzinfo is None:
            promoted_at = promoted_at.replace(tzinfo=timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        effective = window if window is not None else self.rollback_window
        within_window = (current_time - promoted_at) <= effective
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
        zero_touch_real: bool = False,
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
        rollback_window = self.autonomous_real_rollback_window if zero_touch_real else None
        rollback_required = self.should_rollback(
            promoted_at=promoted_at,
            candidate_fitness=candidate_fitness,
            previous_fitness=previous_fitness,
            now=now,
            window=rollback_window,
        )
        return EvolutionGuardDecision(
            mutation_allowed=mutation_allowed,
            signed_approval=signed_approval,
            rollback_required=rollback_required,
            revert_to_hash=str(current_hash) if rollback_required and current_hash else None,
        )
