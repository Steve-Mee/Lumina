"""Phase 2 Autonomy foundation — gated, fail-closed, default disabled.

Scope (v1 foundation)
---------------------
- Advanced / dynamic wall **threshold proposals** (regime + progress), not a second wall engine.
- Self-adaptive **birth recovery** parameters within a safe catalog (no restart).
- In-process **instance adaptation** (handler cfg refresh / plateau / phoenix flags).

Hard rem
--------
- All features default **OFF** (``phase2_autonomy_enabled: false``).
- Multi-gate: master flag → pillar → Perfect Birth flag (or SIM scaffold) →
  constitution → Approval Twin → shadow-if-risk.
- Twin never overrides constitution violations.
- No REAL capital / broker / OS process spawn surfaces.

Out of scope
------------
- Auto-declaring Perfect Birth
- Never-stop at scale KPIs
- REAL PromotionGate / live orders
- Multi-process cluster spawn
- Strategy DNA / risk hyperparameter mutation (use code_evolution / risk shadow)

See ``docs/adr/0034-phase2-autonomy-foundation.md`` and roadmap §7.
"""

from __future__ import annotations

from lumina_core.birth.phase2_autonomy.contracts import (
    Phase2GateReason,
    Phase2GateResult,
    Phase2InstanceAdaptProposal,
    Phase2OrchestratorDecision,
    Phase2ParamAdjustmentProposal,
    Phase2Pillar,
    Phase2WallAdjustmentProposal,
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
    evaluate_pillar_promotion,
    normalize_execution_mode,
)
from lumina_core.birth.phase2_autonomy.metrics import (
    compute_phase2_metrics_snapshot,
    load_phase2_recent_decisions,
    phase2_status_payload,
    record_phase2_decision_monitoring,
)
from lumina_core.birth.phase2_autonomy.orchestrator import (
    Phase2AutonomyOrchestrator,
    build_orchestrator_from_cfg,
)
from lumina_core.birth.phase2_autonomy.param_catalog import (
    BIRTH_SAFE_PARAM_CATALOG,
    FORBIDDEN_PARAM_KEYS,
    apply_param_proposal_to_state,
    propose_param_adjustment,
    validate_param_changes,
)

__all__ = [
    "BIRTH_SAFE_PARAM_CATALOG",
    "FORBIDDEN_PARAM_KEYS",
    "Phase2AutonomyFeatures",
    "Phase2AutonomyOrchestrator",
    "Phase2ExecutionMode",
    "Phase2GateReason",
    "Phase2GateResult",
    "Phase2InstanceAdaptProposal",
    "Phase2OrchestratorDecision",
    "Phase2ParamAdjustmentProposal",
    "Phase2Pillar",
    "Phase2WallAdjustmentProposal",
    "apply_param_proposal_to_state",
    "apply_wall_adjustment_to_thresholds",
    "build_orchestrator_from_cfg",
    "compute_phase2_metrics_snapshot",
    "evaluate_phase2_gate",
    "evaluate_pillar_promotion",
    "load_phase2_recent_decisions",
    "materialize_instance_adapt_payload",
    "normalize_execution_mode",
    "phase2_status_payload",
    "propose_dynamic_wall_adjustment",
    "propose_instance_adapt",
    "propose_param_adjustment",
    "record_phase2_decision_monitoring",
    "validate_param_changes",
]
