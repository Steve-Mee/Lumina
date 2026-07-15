"""Code evolution pipeline: constitution → twin → sandbox → journal/audit/bus.

Fail-closed. Default disabled. Evaluate-only (no live apply).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.audit import get_audit_logger
from lumina_core.code_evolution.constitution import CodeEvolutionConstitution
from lumina_core.code_evolution.journal import CodeEvolutionJournal
from lumina_core.code_evolution.operators import CodeEvolutionController
from lumina_core.code_evolution.proposal import (
    CodeEvolutionCycleResult,
    CodeMutationProposal,
    CodeSandboxEvalResult,
)
from lumina_core.safety.sandboxed_code_executor import SandboxedCodeExecutor

logger = logging.getLogger(__name__)

AUDIT_STREAM = "evolution.code_mutation"


class CodeEvolutionPipeline:
    """Orchestrates one gated cycle of trading-code evolution proposals."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        max_proposals_per_cycle: int = 1,
        mode: str = "sim",
        timeout_s: int = 30,
        controller: CodeEvolutionController | None = None,
        constitution: CodeEvolutionConstitution | None = None,
        sandbox: SandboxedCodeExecutor | None = None,
        journal: CodeEvolutionJournal | None = None,
        twin: Any | None = None,
        event_bus: Any | None = None,
        constitutional_guard: Any | None = None,
        journal_root: Path | str | None = None,
        audit_path: Path | str | None = None,
        require_twin: bool = True,
    ) -> None:
        self.enabled = bool(enabled)
        self.mode = str(mode or "sim").strip().lower()
        self.require_twin = bool(require_twin)
        self.controller = controller or CodeEvolutionController(
            enabled=self.enabled,
            max_proposals_per_cycle=max_proposals_per_cycle,
        )
        # Keep controller enable flag in sync
        self.controller.enabled = self.enabled
        self.constitution = constitution or CodeEvolutionConstitution()
        self.sandbox = sandbox or SandboxedCodeExecutor(timeout_s=timeout_s)
        self.journal = journal or CodeEvolutionJournal(root=journal_root)
        self.twin = twin
        self.event_bus = event_bus
        self.constitutional_guard = constitutional_guard
        self._audit_path = Path(audit_path) if audit_path else Path("state/code_evolution_audit.jsonl")
        try:
            get_audit_logger().register_stream(AUDIT_STREAM, self._audit_path)
        except Exception:
            logger.debug("code_evolution audit stream register best-effort failed", exc_info=True)

        self.metrics: dict[str, int] = {
            "proposals": 0,
            "constitution_blocks": 0,
            "twin_blocks": 0,
            "sandbox_passes": 0,
            "sandbox_fails": 0,
            "cycles": 0,
        }

    def run_cycle(
        self,
        *,
        current_params: dict[str, float] | None = None,
        seed: str | None = None,
    ) -> CodeEvolutionCycleResult:
        self.metrics["cycles"] += 1
        if not self.enabled:
            return CodeEvolutionCycleResult(
                enabled=False,
                proposals=[],
                decisions=[],
                metrics=self._metrics_payload(),
            )

        proposals = self.controller.propose(current_params=current_params, seed=seed)
        decisions: list[dict[str, Any]] = []
        for prop in proposals:
            decisions.append(self._process_proposal(prop))

        return CodeEvolutionCycleResult(
            enabled=True,
            proposals=proposals,
            decisions=decisions,
            metrics=self._metrics_payload(),
        )

    def _process_proposal(self, proposal: CodeMutationProposal) -> dict[str, Any]:
        self.metrics["proposals"] += 1
        ts = datetime.now(timezone.utc).isoformat()
        decision: dict[str, Any] = {
            "proposal_id": proposal.proposal_id,
            "operator": proposal.operator.value,
            "timestamp": ts,
            "constitution_passed": False,
            "twin_recommendation": False,
            "twin_effective": False,
            "sandbox_passed": False,
            "applied": False,
            "reason": "",
            "violations": [],
        }

        # 1) Code constitution (pre-mutation)
        code_guard = self.constitution.check_pre_mutation(proposal, mode=self.mode)
        constitution_payload = {
            "passed": code_guard.passed,
            "violations": code_guard.violation_names,
            "phase": code_guard.check_phase,
        }
        if not code_guard.passed:
            self.metrics["constitution_blocks"] += 1
            decision["reason"] = "constitution_blocked"
            decision["violations"] = code_guard.violation_names
            self._finalize(proposal, decision, constitution_payload, None, None)
            return decision
        decision["constitution_passed"] = True
        proposal = replace(proposal, constitution_passed=True)

        # 2) Optional TradingConstitution / ConstitutionalGuard (DNA-shaped proxy)
        if self.constitutional_guard is not None:
            try:
                dna_proxy = self.constitution.dna_proxy_for_guard(proposal)
                guard_res = self.constitutional_guard.check_pre_mutation(
                    dna_proxy, mode=self.mode, raise_on_fatal=False
                )
                if not getattr(guard_res, "passed", True):
                    self.metrics["constitution_blocks"] += 1
                    names = list(getattr(guard_res, "violation_names", []) or [])
                    decision["reason"] = "trading_constitution_blocked"
                    decision["violations"] = names
                    constitution_payload["trading_guard"] = names
                    self._finalize(proposal, decision, constitution_payload, None, None)
                    return decision
            except Exception as exc:
                self.metrics["constitution_blocks"] += 1
                decision["reason"] = "constitutional_guard_error"
                decision["violations"] = [f"guard_error:{exc}"]
                self._finalize(proposal, decision, constitution_payload, None, None)
                return decision

        # 3) Approval Twin judgment (must run before sandbox when require_twin)
        twin_result: dict[str, Any]
        if self.twin is not None and hasattr(self.twin, "evaluate_code_proposal"):
            try:
                twin_result = dict(self.twin.evaluate_code_proposal(proposal))
            except Exception as exc:
                logger.exception("twin evaluate_code_proposal failed")
                twin_result = {
                    "recommendation": False,
                    "effective_recommendation": False,
                    "confidence": 0.0,
                    "risk_flags": ["twin_error"],
                    "explanation": str(exc)[:200],
                }
        elif self.twin is not None:
            twin_result = {
                "recommendation": False,
                "effective_recommendation": False,
                "confidence": 0.0,
                "risk_flags": ["twin_missing_code_path"],
                "explanation": "twin lacks evaluate_code_proposal",
            }
        elif self.require_twin:
            twin_result = {
                "recommendation": False,
                "effective_recommendation": False,
                "confidence": 0.0,
                "risk_flags": ["twin_required"],
                "explanation": "Approval Twin required before sandbox execution",
            }
        else:
            # Explicit test/dev escape: twin optional only when require_twin=False
            twin_result = {
                "recommendation": True,
                "effective_recommendation": False,
                "confidence": 0.0,
                "risk_flags": [],
                "explanation": "twin_not_required",
            }

        raw_rec = bool(twin_result.get("recommendation", False))
        effective = bool(twin_result.get("effective_recommendation", False))
        decision["twin_recommendation"] = raw_rec
        decision["twin_effective"] = effective
        proposal = replace(proposal, twin_recommendation=raw_rec, twin_effective=effective)

        # Hard vetoes always block sandbox (fail-closed). Shadow mode still allows
        # evaluate-only sandbox when the twin ran cleanly without hard flags —
        # effective_recommendation may remain False (no sole auto-apply).
        hard_flags = {str(f) for f in (twin_result.get("risk_flags") or [])}
        hard_veto = bool(
            hard_flags
            & {
                "twin_error",
                "twin_required",
                "twin_missing_code_path",
            }
        ) or any(f.startswith("constitution_") for f in hard_flags)

        if hard_veto:
            self.metrics["twin_blocks"] += 1
            decision["reason"] = "twin_blocked"
            decision["violations"] = sorted(hard_flags)
            self._finalize(proposal, decision, constitution_payload, twin_result, None)
            return decision

        # 4) Sandbox execution
        sb: CodeSandboxEvalResult
        try:
            sb = self.sandbox.evaluate(
                proposal_id=proposal.proposal_id,
                operator=proposal.operator.value,
                payload=dict(proposal.payload or {}),
                mode=self.mode,
            )
        except Exception as exc:
            sb = CodeSandboxEvalResult(
                proposal_id=proposal.proposal_id,
                passed=False,
                score=0.0,
                violations=["sandbox_invoke_error"],
                input_hash="",
                output_hash="",
                error=str(exc)[:200],
                mode=self.mode,
            )

        decision["sandbox_passed"] = bool(sb.passed)
        if sb.passed:
            self.metrics["sandbox_passes"] += 1
            decision["reason"] = "evaluated_ok"
            proposal = replace(proposal, sandbox_passed=True)
        else:
            self.metrics["sandbox_fails"] += 1
            decision["reason"] = "sandbox_failed"
            decision["violations"] = list(sb.violations)

        # 5) Live apply always blocked in v1
        apply_res = self.journal.try_apply_live(proposal.proposal_id)
        decision["applied"] = bool(apply_res.get("applied"))
        if decision["reason"] == "evaluated_ok":
            decision["reason"] = "evaluated_ok_not_applied"

        self._finalize(proposal, decision, constitution_payload, twin_result, sb)
        self._publish_bus(proposal, decision, sb)
        return decision

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
                    "applied": False,
                }
            )
        except Exception:
            logger.exception("code_evolution journal write failed")

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
                    "applied": False,
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
                "applied": False,
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


def run_code_evolution_dry_cycle(
    *,
    enabled: bool = False,
    max_proposals_per_cycle: int = 1,
    mode: str = "sim",
    twin: Any | None = None,
    event_bus: Any | None = None,
    constitutional_guard: Any | None = None,
    journal_root: Path | str | None = None,
    seed: str | None = None,
    current_params: dict[str, float] | None = None,
    timeout_s: int = 30,
    require_twin: bool = True,
) -> dict[str, Any]:
    """Public entrypoint for gated dry cycle (default disabled)."""
    pipe = CodeEvolutionPipeline(
        enabled=enabled,
        max_proposals_per_cycle=max_proposals_per_cycle,
        mode=mode,
        twin=twin,
        event_bus=event_bus,
        constitutional_guard=constitutional_guard,
        journal_root=journal_root,
        timeout_s=timeout_s,
        require_twin=require_twin,
    )
    result = pipe.run_cycle(current_params=current_params, seed=seed)
    return result.to_dict()
