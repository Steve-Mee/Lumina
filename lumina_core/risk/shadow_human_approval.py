"""Shadow human-approval + experiment history helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.shadow_registry import ShadowRunRegistry
from lumina_core.risk.shadow_types import ShadowContext

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision, ShadowResult

logger = get_logger("lumina.risk.shadow")


class ShadowHumanApprovalMixin:
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

    def list_pending_human_approvals(self) -> list[dict[str, Any]]:
        """
        Convenience method that delegates to the attached/default registry
        (if any) to list experiments currently waiting for human review.

        Returns an empty list if no registry is attached.
        """
        reg = self._registry
        if reg is None:
            return []
        return reg.list_pending_human_approvals()

    def get_human_review_package(self, experiment_id: str) -> dict[str, Any] | None:
        """
        When a registry is attached, assembles a ready-to-review package for a
        pending human approval.

        Returns the human_approval_request (with rich decision_summary) plus
        any other available context. Returns None if no registry or no pending
        human approval for the given experiment.
        """
        reg = self._registry
        if reg is None:
            return None

        request = reg.get(f"{experiment_id}:human_approval_request")
        if request is None:
            return None

        # Also try to get the main run and latest promotion decision for extra context
        run = reg.get(experiment_id)
        latest_decision = None
        for key in [f"{experiment_id}:promotion:human_approval", f"{experiment_id}:promotion:final"]:
            if key in getattr(reg, "_runs", {}):
                latest_decision = reg._runs[key]
                break

        return {
            "experiment_id": experiment_id,
            "human_approval_request": request,
            "original_run": run,
            "latest_promotion_decision": latest_decision,
        }

    def get_experiment_history(self, experiment_id: str) -> list[dict[str, Any]]:
        """
        Returns the complete chronological history of a shadow experiment,
        including the initial run, all promotion decisions, human approval
        request (if any), and final decision.

        This provides a full audit trail for an experiment — extremely useful
        for compliance, post-mortems, and understanding promotion outcomes.
        """
        reg = self._registry
        if reg is None:
            return []

        history = []

        # Main experiment run
        main_run = reg.get(experiment_id)
        if main_run:
            history.append({
                "type": "shadow_run",
                "data": main_run,
            })

        # Human approval request (if exists)
        ha_request = reg.get(f"{experiment_id}:human_approval_request")
        if ha_request:
            history.append({
                "type": "human_approval_request",
                "data": ha_request,
            })

        # All promotion decisions for this experiment
        for key, value in reg._runs.items():
            if key.startswith(f"{experiment_id}:promotion:"):
                history.append({
                    "type": "promotion_decision",
                    "stage": value.get("stage"),
                    "data": value,
                })

        # Human resolution record (if a human decision was submitted)
        resolution = reg.get(f"{experiment_id}:human_resolution")
        if resolution:
            history.append({
                "type": "human_resolution",
                "data": resolution,
            })

        # Sort by timestamp when available
        history.sort(key=lambda x: x["data"].get("timestamp", "") if isinstance(x.get("data"), dict) else "")

        return history

    def get_experiment_resolution(self, experiment_id: str) -> dict[str, Any] | None:
        """
        Returns a clean, high-level summary of the final resolution for a
        shadow experiment (including the human decision and notes if present).

        This is the easiest way to answer "what was the final outcome of this
        shadow experiment and why?"
        """
        reg = self._registry
        if reg is None:
            return None

        # Get the latest promotion decision (final or reject)
        final_decision = None
        for stage in ["final", "reject"]:
            key = f"{experiment_id}:promotion:{stage}"
            if key in getattr(reg, "_runs", {}):
                final_decision = reg._runs[key]
                break

        if final_decision is None:
            # Fall back to the last known promotion decision
            for key in sorted([k for k in getattr(reg, "_runs", {}) if k.startswith(f"{experiment_id}:promotion:")]):
                final_decision = reg._runs[key]

        resolution = reg.get(f"{experiment_id}:human_resolution")

        return {
            "experiment_id": experiment_id,
            "final_promotion_decision": final_decision,
            "human_resolution": resolution,
            "has_human_review": resolution is not None,
        }

    def get_experiment_resolution_summary(self, experiment_id: str) -> dict[str, Any] | None:
        """
        Returns a concise, human-friendly one-pager summary of the entire
        promotion outcome for a shadow experiment.

        Includes key decision points, the recommendation at the time, the
        human decision (if any), and the final result. Perfect for dashboards,
        reports, and quick audits.
        """
        reg = self._registry
        if reg is None:
            return None

        resolution = self.get_experiment_resolution(experiment_id)
        if resolution is None:
            return None

        history = self.get_experiment_history(experiment_id)

        # Extract the most relevant human context
        human_notes = None
        if resolution.get("human_resolution"):
            human_notes = resolution["human_resolution"].get("resolution_notes")

        # Find the recommendation that was active when human review was requested
        for item in history:
            if item["type"] == "promotion_decision" and item.get("stage") == "human_approval":
                # This is a bit indirect; in a real system we'd store it better.
                # For now we rely on the recommendation that was current.
                pass

        return {
            "experiment_id": experiment_id,
            "final_outcome": {
                "stage": resolution["final_promotion_decision"]["stage"] if resolution.get("final_promotion_decision") else None,
                "allowed": resolution["final_promotion_decision"]["allowed"] if resolution.get("final_promotion_decision") else None,
            },
            "human_decision": {
                "approved": resolution["human_resolution"]["approved"] if resolution.get("human_resolution") else None,
                "notes": human_notes,
                "approver": resolution["human_resolution"].get("approver") if resolution.get("human_resolution") else None,
            } if resolution.get("human_resolution") else None,
            "had_human_review": resolution.get("has_human_review", False),
            "history_length": len(history),
        }

    def submit_human_approval_decision(
        self,
        *,
        experiment_id: str,
        approved: bool,
        reason: str,
        approver: str | None = None,
        resolution_notes: str | None = None,
        evidence: dict[str, Any] | None = None,
        registry: ShadowRunRegistry | None = None,
    ) -> "EvolutionPromotionDecision":
        """
        Record the outcome of a human review for a shadow experiment that
        reached the human_approval stage, and emit the next EvolutionPromotionDecision
        (typically with stage="final").

        Supports richer context for better auditability and future tooling:
        - `resolution_notes`: free-text explanation from the human reviewer
        - `evidence`: structured additional data (e.g. links, extra analysis, screenshots)

        This completes the basic human approval workflow tooling for the shadow
        promotion chain.
        """
        from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision as _EvolutionPromotionDecision

        # Look up the previous promotion decision for context (best effort)
        previous_dna_hash = None
        reg = registry or getattr(self, "_registry", None)
        if reg is not None:
            prev_run = reg.get(experiment_id)
            if prev_run:
                previous_dna_hash = prev_run.get("dna_hash")

        next_stage = "final"  # Use "final" for both approved and rejected cases for now (model constraint)

        decision = _EvolutionPromotionDecision(
            dna_hash=previous_dna_hash or experiment_id,
            allowed=approved,
            reason=reason,
            stage=next_stage,
            mode=None,
            evidence_ref=f"human_approval:{experiment_id}",
        )

        # Attach richer human context (we enrich the published payload)
        metadata: dict[str, Any] = {"experiment_id": experiment_id}
        if approver:
            metadata["approver"] = approver
        if resolution_notes:
            metadata["resolution_notes"] = resolution_notes
        if evidence:
            metadata["evidence"] = evidence

        self._publish_event(
            topic="evolution.promotion.decision",
            payload=decision.model_dump(mode="json"),
            metadata=metadata,
        )

        # Record the final decision properly (including richer context)
        if reg is not None:
            try:
                reg.record_promotion_decision(experiment_id, decision)
                # Also store the full enriched payload for auditability
                reg.record(f"{experiment_id}:human_resolution", {
                    "experiment_id": experiment_id,
                    "approved": approved,
                    "reason": reason,
                    "approver": approver,
                    "resolution_notes": resolution_notes,
                    "evidence": evidence,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception:
                pass

        return decision
