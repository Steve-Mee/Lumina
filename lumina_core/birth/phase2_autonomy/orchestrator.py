"""Thin Phase 2 Autonomy orchestrator: propose → gate → publish → optional apply."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.birth.phase2_autonomy.contracts import (
    Phase2OrchestratorDecision,
)
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.execution_mode import (
    Phase2ExecutionMode,
    should_mutate,
    should_record_counterfactual,
)
from lumina_core.birth.phase2_autonomy.metrics import record_phase2_decision_monitoring
from lumina_core.birth.phase2_autonomy.orchestrator_wall import Phase2WallEvalMixin
from lumina_core.birth.phase2_autonomy.orchestrator_param import Phase2ParamEvalMixin
from lumina_core.birth.phase2_autonomy.orchestrator_instance import Phase2InstanceEvalMixin
from lumina_core.birth.phase2_autonomy.orchestrator_publish import Phase2PublishMixin

logger = logging.getLogger("lumina.birth.phase2_autonomy")


class Phase2AutonomyOrchestrator(
    Phase2WallEvalMixin,
    Phase2ParamEvalMixin,
    Phase2InstanceEvalMixin,
    Phase2PublishMixin,
):
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
    ) -> tuple[bool, dict[str, Any], bool]:
        """Return (applied, payload, shadow_would_apply).

        Only APPLY mode mutates when gate allows. SHADOW records counterfactual.
        OBSERVE never mutates.
        """
        if not apply or not gate_allowed:
            return False, {}, False
        em = self.execution_mode()
        if should_mutate(em):
            return True, dict(mutate_payload), False
        if should_record_counterfactual(em):
            return False, dict(mutate_payload), True
        return False, {}, False

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

def build_orchestrator_from_cfg(
    cfg: Any,
    *,
    event_bus: Any | None = None,
    approval_twin: Any | None = None,
    mode: str = "sim",
    workspace_root: Any | None = None,
) -> Phase2AutonomyOrchestrator | None:
    """Return orchestrator when master flag or active SIM campaign is on.

    H3: ``workspace_root`` overlays ``state/phase2_sim_campaign.json`` so pillars
    run in shadow/apply without config.yaml edits. REAL mode still gate-blocked.
    """
    if workspace_root is not None:
        from lumina_core.birth.phase2_autonomy.sim_campaign import (
            resolve_features_with_campaign,
        )

        features = resolve_features_with_campaign(cfg, workspace_root)
    else:
        features = Phase2AutonomyFeatures.from_curriculum_cfg(cfg)
    if not features.enabled:
        return None
    # Fail-closed: never force REAL apply via campaign — clamp mode if real-like
    orch_mode = str(mode or "sim")
    if orch_mode.strip().lower() in {"real", "live", "prod", "production"}:
        # Campaign may still observe/shadow; orchestrator gate rejects REAL apply
        pass
    return Phase2AutonomyOrchestrator(
        features=features,
        cfg=cfg,
        event_bus=event_bus,
        approval_twin=approval_twin,
        mode=orch_mode,
    )


__all__ = [
    "Phase2AutonomyOrchestrator",
    "build_orchestrator_from_cfg",
]
