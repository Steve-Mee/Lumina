"""Birth gen0 DNA resolution and active-DNA bootstrap for evolution cycles."""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from lumina_core.birth.dna_handoff import resolve_birth_gen0_dna
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.mutation_pipeline import MutationPipeline

if TYPE_CHECKING:
    from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator

logger = logging.getLogger(__name__)


def resolve_initial_top_and_active_dna(
    orchestrator: "EvolutionOrchestrator",
    *,
    base_metrics: dict[str, Any],
) -> tuple[list[PolicyDNA], PolicyDNA | None]:
    top_dna = orchestrator._registry.get_ranked_dna(limit=3)
    active_dna = orchestrator._registry.get_latest_dna(version="active")
    if not top_dna and active_dna is None:
        birth_dna = resolve_birth_gen0_dna(orchestrator._registry)
        if birth_dna is not None:
            active_dna = birth_dna
            top_dna = [birth_dna]
        else:
            active_dna = orchestrator._bootstrap_active_dna(base_metrics=base_metrics)
            top_dna = [active_dna]
    return top_dna, active_dna


def bootstrap_active_dna(
    orchestrator: "EvolutionOrchestrator",
    *,
    base_metrics: dict[str, Any],
) -> PolicyDNA:
    orchestrator._mutation_pipeline = MutationPipeline(
        registry=orchestrator._registry,
        constitutional_guard=orchestrator._constitutional_guard,
        logger=logger,
    )
    return orchestrator._mutation_pipeline.bootstrap_active_dna(base_metrics=base_metrics)
