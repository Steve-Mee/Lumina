"""
Shadow Aperture Evaluator for Risk Logic Experiments.

Bounded modules: ``shadow_types``, ``shadow_registry``, ``shadow_isolation``,
``shadow_assessment``, ``shadow_experiment``, ``shadow_human_approval``.

This module remains the public façade (``ShadowRiskEvaluator`` + re-exports).
NO verdict logic changes in Wave A.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from lumina_core.logging_utils import get_logger
from lumina_core.risk.orchestration import RiskOrchestrator
from lumina_core.risk.shadow_assessment import ShadowAssessmentMixin
from lumina_core.risk.shadow_experiment import ShadowExperimentMixin
from lumina_core.risk.shadow_human_approval import ShadowHumanApprovalMixin
from lumina_core.risk.shadow_isolation import ShadowIsolationMixin
from lumina_core.risk.shadow_registry import ShadowRunRegistry  # noqa: F401
from lumina_core.risk.shadow_types import ShadowContext, ShadowExperimentResult  # noqa: F401

if TYPE_CHECKING:
    pass

logger = get_logger("lumina.risk.shadow")


class ShadowRiskEvaluator(
    ShadowIsolationMixin,
    ShadowAssessmentMixin,
    ShadowExperimentMixin,
    ShadowHumanApprovalMixin,
):
    """
    Evaluates risk decisions in a fully isolated shadow aperture.

    Guarantees:
    - Never touches live broker or mutates production state.
    - Uses a dedicated RiskOrchestrator instance (no shared mutable state).
    - All decision_context_ids are forced to start with "shadow-".
    - Emits ShadowResult events for downstream observation.
    """

    def __init__(
        self,
        engine: Any,
        registry: ShadowRunRegistry | None = None,
        *,
        event_bus: Any | None = None,
    ):
        self.engine = engine
        self._shadow_orchestrator: Optional[RiskOrchestrator] = None
        self._isolation_enforced = True  # Permanent guard
        self._registry: ShadowRunRegistry | None = registry
        self._event_bus = (
            event_bus if event_bus is not None else getattr(engine, "event_bus", None)
        )

        # Hard isolation: shadow must never run in a way that could reach live broker paths
        # We treat shadow as its own strict "experiment-only" context.
        from lumina_core.risk.aperture_guard import enforce_no_bypass_in_strict_mode
        enforce_no_bypass_in_strict_mode(
            engine=engine,
            bypass_id="shadow_risk_evaluator",
            caller="ShadowRiskEvaluator.__init__",
            reason="ShadowRiskEvaluator must never share mutable live risk state or reach broker paths",
        )


__all__ = [
    "ShadowContext",
    "ShadowExperimentResult",
    "ShadowRiskEvaluator",
    "ShadowRunRegistry",
]
