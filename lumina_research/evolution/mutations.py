"""Parameter/window genomes → Phase 2 hypothesis drafts. No Risk Core fields."""

from __future__ import annotations

import random

from lumina_core.agent_orchestration.schemas_research import MutationProposed, ParameterGenome
from lumina_research.agents.generators import GeneratorError, HypothesisDraft, HypothesisGenerator
from lumina_research.evolution.regime import RegimeAction, throttled_quantity
from lumina_research.evolution.types import MutationRefused, require_feasible


class DraftGenerator(HypothesisGenerator):
    """Emits a prepared batch of drafts. Count must match exactly."""

    def __init__(self, drafts: tuple[HypothesisDraft, ...], *, generator_id: str = "evolution") -> None:
        self._drafts = drafts
        self._generator_id = generator_id

    @property
    def generator_id(self) -> str:
        return self._generator_id

    def drafts(self, *, rng: random.Random, count: int, start_index: int) -> tuple[HypothesisDraft, ...]:
        del rng, start_index
        if count != len(self._drafts):
            raise GeneratorError("count must equal prepared drafts")
        return self._drafts


def mutation_to_draft(mutation: MutationProposed, *, action: RegimeAction) -> HypothesisDraft:
    """Map an admitted mutation to a Phase 2 draft. Regime may only change quantity."""
    genome = require_feasible(mutation.genome)
    if mutation.kind in {"strategy_switch", "skip_gate", "direct_promotion"}:
        raise MutationRefused("forbidden mutations cannot become hypotheses")
    if mutation.kind in {"threshold_change", "risk_core_change"}:
        raise MutationRefused("protected mutations cannot become hypotheses")
    quantity = throttled_quantity(genome, action)
    return HypothesisDraft(
        config_id=mutation.config_id,
        generator_id="evolution",
        kind=genome.kind,
        instrument=genome.instrument,
        seed=mutation.seed,
        n_obs=genome.n_obs,
        mu=genome.mu,
        sigma=genome.sigma,
        planted=genome.planted,
        proposed_quantity=quantity,
        proposed_price=genome.price,
        proposed_notional=quantity * genome.price,
        rationale=mutation.rationale,
        is_size=genome.is_size,
        oos_size=genome.oos_size,
        parent_config_id=mutation.parent_config_id,
    )


def copy_genome(genome: ParameterGenome, **updates: object) -> ParameterGenome:
    payload = genome.model_dump()
    payload.update(updates)
    return require_feasible(ParameterGenome.model_validate(payload))
