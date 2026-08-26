"""Champion vs challenger gate on the same truthful fitness SSOT."""
from __future__ import annotations

from typing import Any

from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.multi_day_sim_types import SimResult


def champion_challenger_decision(
    *,
    champion: PolicyDNA | None,
    challenger: PolicyDNA,
    challenger_fitness: float,
    previous_fitness: float,
    sim_results: list[SimResult] | None = None,
    min_lift: float = 0.0,
) -> dict[str, Any]:
    """Keep champion unless challenger has finite fitness and beats it.

    Untruthful / fail-closed fitness (-inf) never dethrones a champion.
    REAL capital is not armed here — caller still runs constitution + Twin + PromotionGate.
    """
    _ = sim_results
    champ_fit = float(previous_fitness)
    if champion is not None:
        champ_fit = float(getattr(champion, "fitness_score", previous_fitness) or previous_fitness)
    chal_fit = float(challenger_fitness)
    truthful = chal_fit != float("-inf") and chal_fit == chal_fit  # not NaN
    beats = truthful and chal_fit > (champ_fit + float(min_lift))
    keep_champion = champion is not None and not beats
    return {
        "promote_challenger": bool(beats and not keep_champion),
        "keep_champion": bool(keep_champion),
        "truthful_fitness": truthful,
        "challenger_fitness": chal_fit,
        "champion_fitness": champ_fit,
        "reason": (
            "challenger_wins"
            if beats
            else ("untruthful_fitness" if not truthful else "champion_holds")
        ),
    }


def apply_champion_challenger_gate(
    *,
    champion: PolicyDNA | None,
    challenger: PolicyDNA,
    challenger_fitness: float,
    previous_fitness: float,
    sim_results: list[SimResult] | None = None,
) -> tuple[PolicyDNA, float, dict[str, Any]]:
    decision = champion_challenger_decision(
        champion=champion,
        challenger=challenger,
        challenger_fitness=challenger_fitness,
        previous_fitness=previous_fitness,
        sim_results=sim_results,
    )
    if decision["keep_champion"] and champion is not None:
        return champion, float(decision["champion_fitness"]), decision
    if not decision["truthful_fitness"]:
        return challenger, float("-inf"), decision
    return challenger, float(challenger_fitness), decision
