"""Safety-first rollout framework for evolutionary DNA promotion.

This module enforces a zero-live-risk policy:
- Candidate mutations are evaluated in shadow mode before any REAL promotion.
- Radical mutations require explicit human approval.
- A/B evidence and fitness deltas are logged for auditability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.audit import get_audit_logger
from lumina_core.fault import FaultDomain, FaultPolicy


_DEFAULT_ROLLOUT_AUDIT_PATH = Path("state/evolution_rollout_history.jsonl")
_STREAM_NAME = "evolution.rollout"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class RolloutDecision:
    allow_promotion: bool
    stage: str
    reason: str
    shadow_required: bool
    shadow_passed: bool
    live_orders_blocked: bool
    radical_mutation: bool
    human_approval_required: bool
    human_approval_granted: bool
    ab_verdict: str
    metrics_delta: dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvolutionRolloutFramework:
    """Orchestrates promotion gates for safe mutation rollout."""

    def __init__(
        self,
        *,
        audit_path: Path | None = None,
        radical_delta_abs: float = 0.25,
        radical_delta_ratio: float = 0.35,
    ) -> None:
        self._audit_path = audit_path or _DEFAULT_ROLLOUT_AUDIT_PATH
        self._radical_delta_abs = float(radical_delta_abs)
        self._radical_delta_ratio = float(radical_delta_ratio)
        get_audit_logger().register_stream(_STREAM_NAME, self._audit_path)

    @staticmethod
    def shadow_runtime_flags() -> dict[str, Any]:
        """Canonical execution flags for shadow-only candidate evaluation."""
        return {
            "shadow_mode": True,
        }

    def evaluate_promotion(
        self,
        *,
        mode: str,
        previous_fitness: float,
        winner_fitness: float,
        shadow_status: str,
        shadow_passed: bool,
        explicit_human_approval: bool,
        twin_risk_flags: list[str] | None = None,
        selected_variant: dict[str, Any] | None = None,
        all_variants: list[dict[str, Any]] | None = None,
    ) -> RolloutDecision:
        normalized_mode = str(mode or "sim").strip().lower()
        risk_flags = [str(x) for x in list(twin_risk_flags or []) if str(x).strip()]

        delta = float(winner_fitness) - float(previous_fitness)
        ratio = 0.0
        if previous_fitness not in (0.0, float("-inf")):
            ratio = delta / max(abs(float(previous_fitness)), 1e-9)
        ratio = float(ratio)

        radical = bool(risk_flags or abs(delta) >= self._radical_delta_abs or abs(ratio) >= self._radical_delta_ratio)

        human_required = bool(normalized_mode in {"real", "paper"} and radical)
        human_granted = bool((not human_required) or explicit_human_approval)

        shadow_required = bool(normalized_mode == "real")
        shadow_ready = bool((not shadow_required) or shadow_passed)

        stage = "ready_for_promotion"
        reason = "all_rollout_gates_passed"
        if shadow_required and not shadow_ready:
            stage = "shadow_validation"
            reason = f"shadow_not_complete:{shadow_status}"
        elif human_required and not human_granted:
            stage = "pending_human_approval"
            reason = "radical_mutation_requires_explicit_human_approval"

        allow_promotion = bool(shadow_ready and human_granted)
        ab_verdict = self._derive_ab_verdict(selected_variant=selected_variant, all_variants=all_variants)

        decision = RolloutDecision(
            allow_promotion=allow_promotion,
            stage=stage,
            reason=reason,
            shadow_required=shadow_required,
            shadow_passed=bool(shadow_passed),
            live_orders_blocked=True,
            radical_mutation=radical,
            human_approval_required=human_required,
            human_approval_granted=human_granted,
            ab_verdict=ab_verdict,
            metrics_delta={
                "fitness_delta_abs": float(delta),
                "fitness_delta_ratio": float(ratio),
            },
        )

        self._append_audit(
            {
                "event": "rollout_decision",
                "mode": normalized_mode,
                "shadow_status": str(shadow_status or "unknown"),
                "risk_flags_count": len(risk_flags),
                "risk_flags": risk_flags,
                "selected_variant_score": self._variant_score(selected_variant),
                "ab_variant_count": len(list(all_variants or [])),
                **decision.to_dict(),
            }
        )
        return decision

    def _append_audit(self, payload: dict[str, Any]) -> None:
        mode = str(payload.get("mode", "sim")).strip().lower() or "sim"
        try:
            get_audit_logger().append(
                stream=_STREAM_NAME,
                payload=payload,
                path=self._audit_path,
                mode=mode,
                actor_id="evolution_rollout_framework",
                severity="info",
            )
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            FaultPolicy.handle(
                domain=FaultDomain.EVOLUTION_AUDIT,
                operation="append_rollout_audit",
                exc=exc,
                is_real_mode=(mode == "real"),
                fault_cls=RuntimeError,
                message="Evolution rollout audit append failed",
                context={"path": str(self._audit_path), "mode": mode, "stream": _STREAM_NAME},
            )

    @staticmethod
    def _variant_score(variant: dict[str, Any] | None) -> float | None:
        if not isinstance(variant, dict):
            return None
        raw = variant.get("score")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    def _derive_ab_verdict(
        self,
        *,
        selected_variant: dict[str, Any] | None,
        all_variants: list[dict[str, Any]] | None,
    ) -> str:
        selected_score = self._variant_score(selected_variant)
        if selected_score is None:
            return "unknown"

        scores: list[float] = []
        for variant in list(all_variants or []):
            score = self._variant_score(variant)
            if score is not None:
                scores.append(score)
        if not scores:
            return "unknown"

        baseline = sum(scores) / max(1, len(scores))
        if selected_score > baseline:
            return "variant_beats_ab_mean"
        if selected_score < baseline:
            return "variant_under_ab_mean"
        return "variant_matches_ab_mean"
