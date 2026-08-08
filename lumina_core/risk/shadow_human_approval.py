"""Shadow human-approval + experiment history helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_human_history import ShadowHumanHistoryMixin
from lumina_core.risk.shadow_types import ShadowContext

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision, ShadowResult

logger = get_logger("lumina.risk.shadow")


class ShadowHumanApprovalMixin(ShadowHumanHistoryMixin):
    @staticmethod
    def recommend_promotion_action(
        shadow_result: "ShadowResult",
        comparison: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Produces a structured recommendation for the next step in the promotion flow
        based on the shadow outcome and comparison (if available).

        This is a key piece for making shadow results actionable toward
        promotion_gate / human_approval / final stages.
        """
        verdict = shadow_result.verdict
        has_comparison = comparison is not None

        if verdict != "pass":
            return {
                "suggested_stage": "reject",
                "reason": "shadow_verdict_failed",
                "confidence": "high",
            }

        if not has_comparison:
            return {
                "suggested_stage": "promotion_gate",
                "reason": "shadow_passed_no_reference",
                "confidence": "medium",
            }

        critical_differences = comparison.get("has_differences", False)

        if critical_differences:
            return {
                "suggested_stage": "human_approval",
                "reason": "critical_differences_detected",
                "confidence": "high",
            }

        # Clean pass with matching reference
        return {
            "suggested_stage": "promotion_gate",
            "reason": "shadow_passed_clean_vs_reference",
            "confidence": "high",
        }

    def create_shadow_promotion_decision(
        self,
        context: ShadowContext,
        shadow_result: "ShadowResult",
        comparison: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
    ) -> "EvolutionPromotionDecision":
        """
        Turns the result of a shadow run into an EvolutionPromotionDecision.

        Now respects an optional `recommendation` (from `recommend_promotion_action`)
        to set the appropriate stage ("shadow", "promotion_gate", or "human_approval")
        instead of always defaulting to "shadow".

        This makes the recommendation directly drive progression in the promotion flow.
        """
        from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision as _EvolutionPromotionDecision

        # Basic automated promotion readiness rules
        verdict_ok = shadow_result.verdict == "pass"

        comparison_ok = True
        if comparison:
            critical_mismatches = (
                not comparison.get("policy_match", False) or
                not comparison.get("final_arbitration_match", True)
            )
            comparison_ok = not critical_mismatches

        allowed = verdict_ok and comparison_ok

        if not verdict_ok:
            reason = "shadow_verdict_failed"
        elif comparison and not comparison_ok:
            reason = "critical_differences_vs_live"
        else:
            reason = "shadow_evaluation_passed_clean"

        # Use recommendation to choose stage (if provided)
        if recommendation:
            suggested = recommendation.get("suggested_stage", "shadow")
            if suggested in ("promotion_gate", "human_approval", "shadow"):
                stage = suggested
            else:
                stage = "shadow"
        else:
            stage = "shadow"

        decision = _EvolutionPromotionDecision(
            dna_hash=context.dna_hash,
            allowed=allowed,
            reason=reason,
            stage=stage,
            mode=None,
            evidence_ref=context.decision_context_id,
        )

        # Publish the promotion decision (best-effort)
        self._publish_event(
            topic="evolution.promotion.decision",
            payload=decision.model_dump(mode="json"),
            metadata={"experiment_id": context.experiment_id},
        )

        # Record in registry if available (for pending human approval queries etc.)
        reg = getattr(self, "_registry", None)
        if reg is not None:
            try:
                reg.record_promotion_decision(context.experiment_id, decision)
            except Exception:
                pass

        return decision

    @staticmethod
    def prepare_human_approval_request(
        context: ShadowContext,
        shadow_result: "ShadowResult",
        comparison: dict[str, Any] | None = None,
        recommendation: dict[str, Any] | None = None,
        decision_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Packages all relevant data from a shadow run into a clean, human-reviewer-friendly
        structure intended for the human_approval stage.

        Includes a concise "decision_summary" extracted from the decision_trace so that
        a human reviewer gets the essential outcomes at a glance (policy, risk controller,
        final arbitration) without having to parse the raw trace.
        """
        decision_summary = {}
        if decision_trace:
            if "policy" in decision_trace:
                decision_summary["policy"] = decision_trace["policy"]
            if "risk_controller" in decision_trace:
                decision_summary["risk_controller"] = decision_trace["risk_controller"]
            if "final_arbitration" in decision_trace:
                decision_summary["final_arbitration"] = decision_trace["final_arbitration"]

        return {
            "experiment_id": context.experiment_id,
            "dna_hash": context.dna_hash,
            "shadow_result": {
                "verdict": shadow_result.verdict,
                "sample_size": shadow_result.sample_size,
            },
            "decision_summary": decision_summary,
            "comparison": comparison or {},
            "recommendation": recommendation or {},
            "decision_context_id": context.decision_context_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "requires_human_review": True,
        }






