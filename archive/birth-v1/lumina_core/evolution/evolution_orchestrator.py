"""Backward-compatible exports for split evolution orchestrator modules."""

from __future__ import annotations

from lumina_core.experiments.ab_framework import ABExperimentFramework

from .evolution_guard import EvolutionGuard
from .fitness_evaluator import (
    CAPITAL_GUARD_DD as _CAPITAL_GUARD_DD,
    dream_engine_commit_hints_enabled as _dream_engine_commit_hints_to_bible,
    resolve_dashboard_url as _resolve_dashboard_url,
    resolve_parallel_realities_count as _resolve_parallel_realities_count,
    score_candidate as _score_candidate,
    seed_from_hash as _seed_from_hash,
    utc_file_stamp as _utc_file_stamp,
    utcnow as _utcnow,
)
from .mutation_pipeline import (
    apply_dream_learnings_to_dna_content as _apply_dream_learnings_to_dna_content,
    coerce_dna_content_to_structured_json as _coerce_dna_content_to_structured_json,
)
from .orchestrator import EvolutionOrchestrator, GenerationResult

# Backward-compat private aliases used by tests/importers.
_ = (
    _CAPITAL_GUARD_DD,
    _dream_engine_commit_hints_to_bible,
    _resolve_dashboard_url,
    _resolve_parallel_realities_count,
    _score_candidate,
    _seed_from_hash,
    _utc_file_stamp,
    _utcnow,
    _apply_dream_learnings_to_dna_content,
    _coerce_dna_content_to_structured_json,
)

__all__ = [
    "ABExperimentFramework",
    "EvolutionGuard",
    "EvolutionOrchestrator",
    "GenerationResult",
]
