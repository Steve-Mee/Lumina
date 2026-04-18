from __future__ import annotations

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.genetic_operators import calculate_fitness, crossover, mutate_prompt


def test_mutate_prompt_changes_prompt() -> None:
    prompt = "Prefer HOLD when signals conflict."
    mutated = mutate_prompt(prompt, 0.3)

    assert mutated != prompt
    assert "HOLD" in mutated


def test_crossover_combines_parent_text() -> None:
    parent1 = PolicyDNA.create(
        prompt_id="policy",
        version="candidate",
        content={"prompt_tweak": "Preserve capital first. Reduce exposure under drift."},
        fitness_score=1.0,
        generation=1,
    )
    parent2 = PolicyDNA.create(
        prompt_id="policy",
        version="candidate",
        content={"prompt_tweak": "Increase conviction only on consensus. Prefer lower drawdown routes."},
        fitness_score=1.2,
        generation=1,
    )

    crossed = crossover(parent1, parent2)

    assert "Preserve capital first" in crossed
    assert "Prefer lower drawdown routes" in crossed


def test_calculate_fitness_fail_closed_on_drawdown() -> None:
    assert calculate_fitness(1000.0, 30000.0, 1.5) == float("-inf")
