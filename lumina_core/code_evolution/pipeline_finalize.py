"""Finalize / apply / bus publish for code evolution (M5 extract)."""
from __future__ import annotations

import logging
from typing import Any

from lumina_core.audit import get_audit_logger
from lumina_core.code_evolution.proposal import CodeMutationProposal, CodeSandboxEvalResult

logger = logging.getLogger(__name__)

AUDIT_STREAM = "evolution.code_mutation"


class CodeEvolutionFinalizeMixin:
    def _maybe_apply_sandbox(
        self,
        proposal: CodeMutationProposal,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """Run apply gate; fail-closed default (apply_disabled)."""
        if not decision.get("sandbox_passed"):
            return {
                "applied": False,
                "reason": "sandbox_not_passed",
                "proposal_id": proposal.proposal_id,
            }
        # Evaluate-only default: do not treat as promotion failure noise
        if not self.apply_policy.apply_enabled:
            return {
                "applied": False,
                "reason": "apply_disabled",
                "fail_reasons": ["apply_disabled"],
                "proposal_id": proposal.proposal_id,
            }
        human_ok, human_approver = self._apply_gate.is_human_approved(proposal.proposal_id)
        # Constitution pre-promotion (H5 gates)
        promo = self.constitution.check_pre_promotion(
            proposal,
            mode=self.mode,
            sandbox_passed=bool(decision.get("sandbox_passed")),
            apply_enabled=True,
            human_approved=human_ok,
            twin_recommendation=bool(decision.get("twin_recommendation")),
            allow_twin_judgment_apply=bool(self.apply_policy.allow_twin_judgment_apply),
            capital_mode=self.mode,
        )
        if not promo.passed:
            return {
                "applied": False,
                "reason": "pre_promotion_blocked",
                "fail_reasons": list(promo.violation_names),
                "proposal_id": proposal.proposal_id,
            }
        return self.journal.try_apply_live(
            proposal.proposal_id,
            evidence={
                "capital_mode": self.mode,
                "constitution_passed": bool(decision.get("constitution_passed")),
                "sandbox_passed": bool(decision.get("sandbox_passed")),
                "twin_recommendation": bool(decision.get("twin_recommendation")),
                "twin_effective": bool(decision.get("twin_effective")),
                "human_approved": human_ok,
                "human_approver": human_approver,
            },
            policy=self.apply_policy,
        )

    def _write_bundle_only(
        self,
        proposal: CodeMutationProposal,
        decision: dict[str, Any],
        constitution_payload: dict[str, Any],
        twin_result: dict[str, Any] | None,
        sandbox_result: CodeSandboxEvalResult | None,
    ) -> None:
        try:
            self.journal.write_bundle(
                proposal,
                constitution_result=constitution_payload,
                twin_result=twin_result,
                sandbox_result=sandbox_result,
                final_decision=decision,
            )
        except Exception:
            logger.exception("code_evolution early journal write failed")

    def _finalize(
        self,
        proposal: CodeMutationProposal,
        decision: dict[str, Any],
        constitution_payload: dict[str, Any],
        twin_result: dict[str, Any] | None,
        sandbox_result: CodeSandboxEvalResult | None,
    ) -> None:
        try:
            self.journal.write_bundle(
                proposal,
                constitution_result=constitution_payload,
                twin_result=twin_result,
                sandbox_result=sandbox_result,
                final_decision=decision,
            )
            self.journal.append_event(
                {
                    "event": "code_evolution.decision",
                    "proposal_id": proposal.proposal_id,
                    "reason": decision.get("reason"),
                    "constitution_passed": decision.get("constitution_passed"),
                    "sandbox_passed": decision.get("sandbox_passed"),
                    "applied": bool(decision.get("applied")),
                }
            )
        except Exception:
            logger.exception("code_evolution journal write failed")

        applied = bool(decision.get("applied"))
        try:
            get_audit_logger().append(
                stream=AUDIT_STREAM,
                payload={
                    "proposal_id": proposal.proposal_id,
                    "operator": proposal.operator.value,
                    "target": proposal.target,
                    "constitution_passed": decision.get("constitution_passed"),
                    "twin_recommendation": decision.get("twin_recommendation"),
                    "twin_effective": decision.get("twin_effective"),
                    "sandbox_passed": decision.get("sandbox_passed"),
                    "applied": applied,
                    "apply_target": "sandbox_store" if applied else None,
                    "reason": decision.get("reason"),
                    "violations": decision.get("violations") or [],
                    "sandbox_input_hash": getattr(sandbox_result, "input_hash", "") if sandbox_result else "",
                    "sandbox_output_hash": getattr(sandbox_result, "output_hash", "") if sandbox_result else "",
                },
                path=self._audit_path,
                mode=self.mode,
                actor_id="code_evolution_pipeline",
                correlation_id=proposal.proposal_id,
                severity="info" if decision.get("sandbox_passed") else "warning",
            )
        except Exception:
            logger.exception("code_evolution audit append failed")

        # Bus: proposal created (best-effort)
        self._publish_topic(
            "evolution.code.proposal.created",
            {
                "proposal_id": proposal.proposal_id,
                "operator": proposal.operator.value,
                "target": proposal.target,
                "description": proposal.description,
                "estimated_loc": proposal.estimated_loc,
                "decision_context_id": proposal.decision_context_id,
                "constitution_passed": decision.get("constitution_passed", False),
                "sandbox_passed": decision.get("sandbox_passed", False),
            },
        )
        if sandbox_result is not None:
            self._publish_topic(
                "evolution.code.sandbox.result",
                {
                    "proposal_id": sandbox_result.proposal_id,
                    "passed": sandbox_result.passed,
                    "score": sandbox_result.score,
                    "violations": list(sandbox_result.violations),
                    "input_hash": sandbox_result.input_hash,
                    "output_hash": sandbox_result.output_hash,
                    "timed_out": sandbox_result.timed_out,
                    "error": sandbox_result.error,
                    "mode": sandbox_result.mode,
                },
            )
        self._publish_topic(
            "evolution.code.decision",
            {
                "proposal_id": proposal.proposal_id,
                "constitution_passed": bool(decision.get("constitution_passed")),
                "twin_recommendation": bool(decision.get("twin_recommendation")),
                "twin_effective": bool(decision.get("twin_effective")),
                "sandbox_passed": bool(decision.get("sandbox_passed")),
                "applied": applied,
                "reason": str(decision.get("reason") or ""),
                "violations": list(decision.get("violations") or []),
                "timestamp": str(decision.get("timestamp") or ""),
            },
        )

    def _publish_bus(
        self,
        proposal: CodeMutationProposal,
        decision: dict[str, Any],
        sandbox_result: CodeSandboxEvalResult,
    ) -> None:
        # Already handled in _finalize; kept for clarity/extension.
        del proposal, decision, sandbox_result

    def _publish_topic(self, topic: str, payload: dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        try:
            if hasattr(self.event_bus, "publish_validated"):
                self.event_bus.publish_validated(
                    topic=topic,
                    producer="code_evolution.pipeline",
                    payload=payload,
                )
            elif hasattr(self.event_bus, "publish"):
                self.event_bus.publish(topic=topic, producer="code_evolution.pipeline", payload=payload)
        except Exception:
            logger.debug("code_evolution bus publish failed topic=%s", topic, exc_info=True)

    def _metrics_payload(self) -> dict[str, Any]:
        out = dict(self.metrics)
        out.update(self.controller.metrics_payload())
        return out


