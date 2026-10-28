"""Phase2InstanceEvalMixin (M5 phase2 orchestrator extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.phase2_autonomy.contracts import (
    Phase2OrchestratorDecision,
    Phase2Pillar,
)
from lumina_core.birth.phase2_autonomy.gates import evaluate_phase2_gate
from lumina_core.birth.phase2_autonomy.instance_adapter import (
    materialize_instance_adapt_payload,
    propose_instance_adapt,
)


class Phase2InstanceEvalMixin:
    def evaluate_instance_adapt(
        self,
        *,
        correlation_id: str = "",
        stage: str = "",
        adaptation_tier: int = 0,
        retries_this_stage: int = 0,
        plateau_active: bool = False,
        phoenix_eligible: bool = False,
        learning_health: str = "flat",
        stall_reason: str = "",
        constitution_violations: int = 0,
        apply: bool = False,
    ) -> Phase2OrchestratorDecision:
        proposal = propose_instance_adapt(
            adaptation_tier=adaptation_tier,
            retries_this_stage=retries_this_stage,
            plateau_active=plateau_active,
            phoenix_eligible=phoenix_eligible,
            learning_health=learning_health,
            stall_reason=stall_reason,
        )
        self._publish_proposal(
            pillar=Phase2Pillar.INSTANCE_ADAPT,
            correlation_id=correlation_id,
            stage=stage,
            proposal=proposal.to_dict(),
        )
        require_apply = self._require_apply_path(apply)
        gate = evaluate_phase2_gate(
            features=self.features,
            pillar=Phase2Pillar.INSTANCE_ADAPT,
            constitution_violations=constitution_violations,
            mode=self.mode,
            approval_twin=self.approval_twin if require_apply else None,
            proposal=proposal,
            require_apply_path=require_apply,
        )
        self._publish_gate(correlation_id=correlation_id, stage=stage, gate=gate)

        mutate_payload: dict[str, Any] = {}
        if apply and gate.allowed:
            mutate_payload = materialize_instance_adapt_payload(proposal)
        applied, apply_payload, shadow_would = self._resolve_apply(
            apply=apply,
            gate_allowed=bool(gate.allowed),
            mutate_payload=mutate_payload,
        )

        decision = Phase2OrchestratorDecision(
            pillar=Phase2Pillar.INSTANCE_ADAPT.value,
            proposal=proposal.to_dict(),
            gate=gate,
            applied=applied,
            apply_payload=apply_payload,
        )
        self._audit_decision(
            decision,
            correlation_id=correlation_id,
            stage=stage,
            constitution_violations=constitution_violations,
            apply_requested=apply,
            recovery_tag="instance",
            shadow_would_apply=shadow_would,
        )
        return decision


