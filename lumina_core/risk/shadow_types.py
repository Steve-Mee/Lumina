"""Shadow risk evaluation typed data contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lumina_core.agent_orchestration.schemas import EvolutionPromotionDecision, ShadowResult


@dataclass(slots=True)
class ShadowContext:
    """Context for a single shadow evaluation run."""

    experiment_id: str
    dna_hash: str
    decision_context_id: str  # Must be prefixed with "shadow-" for isolation
    market_data: dict[str, Any]  # Replay or live-read-only market snapshot
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ShadowExperimentResult:
    """Clean, typed return value from a complete shadow experiment run.

    This replaces the previous raw dict return from run_shadow_experiment,
    improving code quality, type safety, and usability.
    """

    experiment_id: str
    dna_hash: str
    shadow_result: "ShadowResult"
    decision_trace: dict[str, Any]
    comparison: dict[str, Any] | None
    promotion_decision: "EvolutionPromotionDecision"
    recommendation: dict[str, Any]  # Suggested next action in the promotion flow
    success: bool
    human_approval_request: dict[str, Any] | None = None  # Populated when recommendation requires human review
