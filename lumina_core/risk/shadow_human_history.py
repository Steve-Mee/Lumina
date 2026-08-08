"""History/resolution helpers for ShadowHumanApprovalMixin (global residual)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lumina_core.risk.shadow_registry import ShadowRunRegistry

class ShadowHumanHistoryMixin:
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
