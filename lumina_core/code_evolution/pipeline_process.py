"""Process single code-evolution proposal (M5 extract)."""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from lumina_core.code_evolution.proposal import CodeMutationProposal, CodeSandboxEvalResult

logger = logging.getLogger(__name__)


class CodeEvolutionProcessMixin:
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

        # 5) Persist bundle before optional apply (REVERT + proposal evidence)
        self._write_bundle_only(proposal, decision, constitution_payload, twin_result, sb)

        # 6) H5 controlled apply → sandbox store only (never live tree)
        apply_res = self._maybe_apply_sandbox(proposal, decision)
        decision["applied"] = bool(apply_res.get("applied"))
        decision["apply"] = {
            k: apply_res.get(k)
            for k in ("reason", "fail_reasons", "paths", "store", "gate")
            if k in apply_res
        }
        if decision["applied"]:
            self.metrics["sandbox_applies"] += 1
            decision["reason"] = "applied_sandbox_store"
        elif decision.get("reason") == "evaluated_ok":
            self.metrics["apply_blocks"] += 1
            decision["reason"] = str(apply_res.get("reason") or "evaluated_ok_not_applied")

        self._finalize(proposal, decision, constitution_payload, twin_result, sb)
        self._publish_bus(proposal, decision, sb)
        return decision

