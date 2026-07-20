"""Thin Phase 2 Autonomy orchestrator: propose → gate → publish → optional apply."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.birth.adaptive_parameter_manager import WallAdaptationState
from lumina_core.birth.phase2_autonomy.contracts import (
    Phase2GateResult,
    Phase2OrchestratorDecision,
    Phase2Pillar,
)
from lumina_core.birth.phase2_autonomy.dynamic_wall import (
    apply_wall_adjustment_to_thresholds,
    propose_dynamic_wall_adjustment,
)
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.gates import evaluate_phase2_gate
from lumina_core.birth.phase2_autonomy.instance_adapter import (
    materialize_instance_adapt_payload,
    propose_instance_adapt,
)
from lumina_core.birth.phase2_autonomy.execution_mode import (
    Phase2ExecutionMode,
    should_mutate,
    should_record_counterfactual,
)
from lumina_core.birth.phase2_autonomy.metrics import record_phase2_decision_monitoring
from lumina_core.birth.phase2_autonomy.param_catalog import (
    apply_param_proposal_to_state,
    propose_param_adjustment,
)

logger = logging.getLogger("lumina.birth.phase2_autonomy")


class Phase2AutonomyOrchestrator:
    """Fail-closed thin orchestration for Phase 2 pillars.

    When features.enabled is False, all evaluate_* methods return rejected
    decisions without publishing and without mutating state.

    Truth layer (Slice B): every evaluate_* with master enabled records to
    ``state/monitoring_phase2_autonomy.jsonl``.

    Execution mode (Slice D): observe | shadow | apply — only apply mutates.
    """

    def __init__(
        self,
        *,
        features: Phase2AutonomyFeatures | None = None,
        cfg: Any | None = None,
        event_bus: Any | None = None,
        approval_twin: Any | None = None,
        mode: str = "sim",
        audit_enabled: bool = True,
    ) -> None:
        self.cfg = cfg
        if features is not None:
            self.features = features
        elif cfg is not None:
            self.features = Phase2AutonomyFeatures.from_curriculum_cfg(cfg)
        else:
            self.features = Phase2AutonomyFeatures()
        self.event_bus = event_bus
        self.approval_twin = approval_twin
        self.mode = str(mode or "sim")
        self.audit_enabled = bool(audit_enabled)

    def is_active(self) -> bool:
        return bool(self.features.enabled)

    def execution_mode(self) -> Phase2ExecutionMode:
        return self.features.execution_mode_enum()

    def _require_apply_path(self, apply: bool) -> bool:
        """Twin/constitution apply path for shadow (counterfactual) and apply modes."""
        if not apply:
            return False
        em = self.execution_mode()
        return em in {Phase2ExecutionMode.SHADOW, Phase2ExecutionMode.APPLY}

    def _resolve_apply(
        self,
        *,
        apply: bool,
        gate_allowed: bool,
        mutate_payload: dict[str, Any],
    ) -> tuple[bool, dict[str, Any], bool, str]:
        """Return (applied, payload, shadow_would_apply, effective_reason_suffix).

        Only APPLY mode mutates when gate allows. SHADOW records counterfactual.
        OBSERVE never mutates.
        """
        if not apply or not gate_allowed:
            return False, {}, False, ""
        em = self.execution_mode()
        if should_mutate(em):
            return True, dict(mutate_payload), False, ""
        if should_record_counterfactual(em):
            return False, dict(mutate_payload), True, "shadow_would_apply"
        # observe
        return False, {}, False, "execution_mode_observe"

    def _audit_decision(
        self,
        decision: Phase2OrchestratorDecision,
        *,
        correlation_id: str,
        stage: str,
        constitution_violations: int,
        apply_requested: bool,
        recovery_tag: str = "",
        shadow_would_apply: bool = False,
    ) -> None:
        """Best-effort JSONL audit when master flag is on (or apply was requested)."""
        if not self.audit_enabled:
            return
        if not self.features.enabled and not apply_requested:
            return
        gate = decision.gate
        try:
            record_phase2_decision_monitoring(
                pillar=decision.pillar,
                allowed=bool(gate.allowed) if gate else False,
                reason=str(gate.reason) if gate else "no_gate",
                applied=bool(decision.applied),
                correlation_id=correlation_id,
                stage=stage,
                twin_conf=float(gate.twin_confidence) if gate else 0.0,
                twin_mode=str(gate.twin_mode) if gate else "",
                mode=self.mode,
                proposal=decision.proposal,
                constitution_violations=constitution_violations,
                message=str(gate.message) if gate else "",
                apply_requested=apply_requested,
                recovery_tag=recovery_tag,
                execution_mode=self.execution_mode().value,
                shadow_would_apply=shadow_would_apply,
            )
        except Exception:
            logger.debug("phase2 audit record best-effort failed", exc_info=True)

    def evaluate_dynamic_wall(
        self,
        *,
        correlation_id: str = "",
        stage: str = "",
        stage_trades: int = 0,
        required: int = 0,
        winrate_slope: float = 0.0,
        winrate_stagnation_count: int = 0,
        hold_stagnation_count: int = 0,
        elapsed_stage_sec: float = 0.0,
        regime: str | None = None,
        constitution_violations: int = 0,
        apply: bool = False,
    ) -> Phase2OrchestratorDecision:
        proposal = propose_dynamic_wall_adjustment(
            stage=stage,
            stage_trades=stage_trades,
            required=required,
            winrate_slope=winrate_slope,
            winrate_stagnation_count=winrate_stagnation_count,
            hold_stagnation_count=hold_stagnation_count,
            elapsed_stage_sec=elapsed_stage_sec,
            regime=regime,
            cfg=self.cfg,
        )
        self._publish_proposal(
            pillar=Phase2Pillar.DYNAMIC_WALL,
            correlation_id=correlation_id,
            stage=stage,
            proposal=proposal.to_dict(),
        )
        require_apply = self._require_apply_path(apply)
        gate = evaluate_phase2_gate(
            features=self.features,
            pillar=Phase2Pillar.DYNAMIC_WALL,
            constitution_violations=constitution_violations,
            mode=self.mode,
            approval_twin=self.approval_twin if require_apply else None,
            proposal=proposal,
            require_apply_path=require_apply,
        )
        self._publish_gate(correlation_id=correlation_id, stage=stage, gate=gate)

        mutate_payload: dict[str, Any] = {}
        if apply and gate.allowed:
            base_wall = 600.0
            wr_stag = 3
            hold_stag = 3
            if self.cfg is not None:
                base_wall = float(
                    getattr(self.cfg, "certified_stage_stall_wall_sec", base_wall) or base_wall
                )
                wr_stag = int(
                    getattr(self.cfg, "stage1_winrate_stagnation_rollouts", wr_stag) or wr_stag
                )
                hold_stag = int(
                    getattr(self.cfg, "stage2_hold_stagnation_rollouts", hold_stag) or hold_stag
                )
            mutate_payload = apply_wall_adjustment_to_thresholds(
                base_stall_wall_sec=base_wall,
                base_winrate_stagnation_rollouts=wr_stag,
                base_hold_stagnation_rollouts=hold_stag,
                proposal=proposal,
            )
        applied, apply_payload, shadow_would, _ = self._resolve_apply(
            apply=apply,
            gate_allowed=bool(gate.allowed),
            mutate_payload=mutate_payload,
        )

        decision = Phase2OrchestratorDecision(
            pillar=Phase2Pillar.DYNAMIC_WALL.value,
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
            recovery_tag="wall",
            shadow_would_apply=shadow_would,
        )
        return decision

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
        applied, apply_payload, shadow_would, _ = self._resolve_apply(
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
            cfg=self.cfg,
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
        applied, apply_payload, shadow_would, _ = self._resolve_apply(
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

    def _publish_proposal(
        self,
        *,
        pillar: Phase2Pillar,
        correlation_id: str,
        stage: str,
        proposal: dict[str, Any],
    ) -> None:
        if self.event_bus is None or not self.features.enabled:
            return
        try:
            from lumina_core.birth.birth_bus_choreography import (
                publish_phase2_instance_proposal,
                publish_phase2_param_proposal,
                publish_phase2_wall_proposal,
            )

            if pillar == Phase2Pillar.DYNAMIC_WALL:
                publish_phase2_wall_proposal(
                    self.event_bus,
                    producer="birth.phase2_autonomy",
                    correlation_id=correlation_id,
                    stage=stage,
                    proposal=proposal,
                )
            elif pillar == Phase2Pillar.SELF_ADAPTIVE_PARAMS:
                publish_phase2_param_proposal(
                    self.event_bus,
                    producer="birth.phase2_autonomy",
                    correlation_id=correlation_id,
                    stage=stage,
                    proposal=proposal,
                )
            elif pillar == Phase2Pillar.INSTANCE_ADAPT:
                publish_phase2_instance_proposal(
                    self.event_bus,
                    producer="birth.phase2_autonomy",
                    correlation_id=correlation_id,
                    stage=stage,
                    proposal=proposal,
                )
        except Exception:
            logger.debug("phase2 publish proposal best-effort failed", exc_info=True)

    def _publish_gate(
        self,
        *,
        correlation_id: str,
        stage: str,
        gate: Phase2GateResult,
    ) -> None:
        if self.event_bus is None or not self.features.enabled:
            return
        try:
            from lumina_core.birth.birth_bus_choreography import publish_phase2_gate_result

            publish_phase2_gate_result(
                self.event_bus,
                producer="birth.phase2_autonomy",
                correlation_id=correlation_id,
                stage=stage,
                gate=gate.to_dict(),
            )
        except Exception:
            logger.debug("phase2 publish gate best-effort failed", exc_info=True)


def build_orchestrator_from_cfg(
    cfg: Any,
    *,
    event_bus: Any | None = None,
    approval_twin: Any | None = None,
    mode: str = "sim",
) -> Phase2AutonomyOrchestrator | None:
    """Return orchestrator only when master flag is on; else None (zero overhead)."""
    features = Phase2AutonomyFeatures.from_curriculum_cfg(cfg)
    if not features.enabled:
        return None
    return Phase2AutonomyOrchestrator(
        features=features,
        cfg=cfg,
        event_bus=event_bus,
        approval_twin=approval_twin,
        mode=mode,
    )


__all__ = [
    "Phase2AutonomyOrchestrator",
    "build_orchestrator_from_cfg",
]
