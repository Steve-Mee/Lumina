"""ProposalGenerator façade — public import path for self-evolution proposals.

Bounded modules: ``proposal_builders`` (challenger/genetic construction),
``proposal_emit`` (risk-shadow + DNA registry wiring). Public symbols remain
importable from this module.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..evolution.dna_registry import DNARegistry
from .proposal_builders import ProposalBuildersMixin
from .proposal_emit import ProposalEmitMixin


class _ProposalOwner(Protocol):
    engine: Any
    dna_registry: DNARegistry
    blackboard: Any | None
    sim_mode: bool
    aggressive_evolution: bool
    max_mutation_depth: str


class ProposalGeneratorProtocol(Protocol):
    def current_champion(self) -> dict[str, Any]: ...

    def build_challengers(self, champion: dict[str, Any], meta_review: dict[str, Any]) -> list[dict[str, Any]]: ...


class ProposalGenerator(ProposalBuildersMixin, ProposalEmitMixin):
    def __init__(self, owner: _ProposalOwner) -> None:
        self._owner = owner

    def dna_registry(self) -> DNARegistry:
        return self._owner.dna_registry


__all__ = ["ProposalGenerator", "ProposalGeneratorProtocol"]
