"""Phase2ParamEvalMixin (M5 phase2 orchestrator extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.adaptive_parameter_manager import WallAdaptationState
from lumina_core.birth.phase2_autonomy.contracts import (
    Phase2OrchestratorDecision,
    Phase2Pillar,
)
from lumina_core.birth.phase2_autonomy.gates import evaluate_phase2_gate
from lumina_core.birth.phase2_autonomy.param_catalog import (
    apply_param_proposal_to_state,
    propose_param_adjustment,
)


class Phase2ParamEvalMixin:
    def evaluate_param_adjustment(
        self,
        *,
        correlation_id: str = "",
        stage: str = "",
        learning_health: str = "flat",
        current_winrate_window: int = 12,
        current_reward_window: int = 12,
        adaptation_tier: int = 0,
        post_volume_gate: bool = False,
        constitution_violations: int = 0,
        wall_state: WallAdaptationState | None = None,
        apply: bool = False,
    ) -> Phase2OrchestratorDecision:
        proposal = propose_param_adjustment(
            learning_health=learning_health,
            current_winrate_window=current_winrate_window,
            current_reward_window=current_reward_window,
            cfg=self.cfg,
            adaptation_tier=adaptation_tier,
            post_volume_gate=post_volume_gate,
        )
        self._publish_proposal(
            pillar=Phase2Pillar.SELF_ADAPTIVE_PARAMS,
            correlation_id=correlation_id,
            stage=stage,
            proposal=proposal.to_dict(),
        )
        require_apply = self._require_apply_path(apply)
        gate = evaluate_phase2_gate(
            features=self.features,
            pillar=Phase2Pillar.SELF_ADAPTIVE_PARAMS,
            constitution_violations=constitution_violations,
            mode=self.mode,
            approval_twin=self.approval_twin if require_apply else None,
            proposal=proposal,
            require_apply_path=require_apply,
        )
        self._publish_gate(correlation_id=correlation_id, stage=stage, gate=gate)

        mutate_payload: dict[str, Any] = {}
        if apply and gate.allowed:
            mutate_payload = {"changes": dict(proposal.changes)}
            if wall_state is not None:
                mutate_payload.update(
                    {
                        "effective_winrate_window": wall_state.effective_winrate_window,
                        "effective_reward_window": wall_state.effective_reward_window,
                    }
                )
        applied, apply_payload, shadow_would = self._resolve_apply(
            apply=apply,
            gate_allowed=bool(gate.allowed),
            mutate_payload=mutate_payload,
        )
        if applied and wall_state is not None:
            apply_param_proposal_to_state(wall_state, proposal)
            apply_payload = {
                "effective_winrate_window": wall_state.effective_winrate_window,
                "effective_reward_window": wall_state.effective_reward_window,
                "changes": dict(proposal.changes),
            }

        decision = Phase2OrchestratorDecision(
            pillar=Phase2Pillar.SELF_ADAPTIVE_PARAMS.value,
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
            recovery_tag="param",
            shadow_would_apply=shadow_would,
        )
        return decision


