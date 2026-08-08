"""Generation cycle result types for EvolutionOrchestrator."""
from __future__ import annotations

from dataclasses import dataclass, field

from .fitness_evaluator import utcnow as _utcnow


@dataclass(slots=True)
class GenerationResult:
    generation: int
    candidate_count: int
    winner_hash: str
    winner_fitness: float
    previous_fitness: float
    promoted: bool
    generated_tested: int = 0
    generated_winners: int = 0
    neuro_tested: int = 0
    neuro_winners: int = 0
    timestamp: str = field(default_factory=_utcnow)


__all__ = ["GenerationResult"]
