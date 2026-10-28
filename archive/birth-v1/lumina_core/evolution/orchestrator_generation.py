"""EvolutionOrchestrator generation / fitness coordination mixin (Wave B PR-B2).

Implementation split (Wave D):
- generation_types.GenerationResult
- generation_nightly.OrchestratorNightlyMixin
- generation_neuro_cycle.OrchestratorNeuroCycleMixin
- generation_strategy_cycle.OrchestratorStrategyCycleMixin
"""
from __future__ import annotations

from .generation_neuro_cycle import OrchestratorNeuroCycleMixin
from .generation_nightly import OrchestratorNightlyMixin
from .generation_strategy_cycle import OrchestratorStrategyCycleMixin
from .generation_types import GenerationResult

__all__ = ["GenerationResult", "OrchestratorGenerationMixin"]


class OrchestratorGenerationMixin(
    OrchestratorNightlyMixin,
    OrchestratorNeuroCycleMixin,
    OrchestratorStrategyCycleMixin,
):
    """Generation run / fitness coordination surface for EvolutionOrchestrator."""
