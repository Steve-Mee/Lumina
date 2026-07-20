"""Phase 2 Autonomy — gated, fail-closed, default disabled.

Public surface (keep small — Slice E)
------------------------------------
- Features + gate + orchestrator
- Pure proposers (wall / params / instance)
- Metrics + execution mode
- Handler hooks for WallAdaptationHandler only

Hard rem
--------
- All features default **OFF**
- Gate: master → pillar → Perfect Birth evidence → constitution → twin → shadow-if-risk
- ``phase2_execution_mode``: observe | shadow | apply (only apply mutates)
- Twin never overrides constitution; REAL apply forbidden

Explicit non-goals (do not grow this package into these)
-------------------------------------------------------
- ML wall policy / second wall engine
- OS multi-process / broker / REAL order spawn
- Auto-declare Perfect Birth without KPI conjunction
- code_evolution / DNA risk mutation (ADR-0033 / risk shadow)
- Imports from stage_loop (hooks only via WallAdaptationHandler)

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
from lumina_core.birth.phase2_autonomy.execution_mode import (
    Phase2ExecutionMode,
    evaluate_pillar_promotion,
    normalize_execution_mode,
)
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.gates import evaluate_phase2_gate
from lumina_core.birth.phase2_autonomy.instance_adapter import (
    materialize_instance_adapt_payload,
    propose_instance_adapt,
)
from lumina_core.birth.phase2_autonomy.metrics import (
    compute_phase2_metrics_snapshot,
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
    "materialize_instance_adapt_payload",
    "normalize_execution_mode",
    "phase2_status_payload",
    "propose_dynamic_wall_adjustment",
    "propose_instance_adapt",
    "propose_param_adjustment",
    "record_phase2_decision_monitoring",
    "validate_param_changes",
]
