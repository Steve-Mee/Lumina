"""Never-stop SIM research cycle — catalog seeds + champion-challenger on fitness SSOT."""
from __future__ import annotations

import logging
from typing import Any

from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA
from lumina_core.evolution.multi_day_sim_types import SimResult
from lumina_core.evolution.research_lab.catalog import inject_catalog_challengers
from lumina_core.evolution.research_lab.champion_challenger import apply_champion_challenger_gate

logger = logging.getLogger(__name__)


def research_lab_enabled(mode: str) -> bool:
    """Research lab runs in SIM/birth only. Never a REAL capital path."""
    return str(mode or "").strip().lower() not in {"real", "live", "prod"}


def merge_catalog_challengers(
    registry: DNARegistry,
    candidates: list[PolicyDNA],
    *,
    generation_offset: int,
    mode: str,
) -> list[PolicyDNA]:
    if not research_lab_enabled(mode):
        return list(candidates)
    try:
        return inject_catalog_challengers(
            registry, candidates, generation_offset=generation_offset, max_inject=2
        )
    except Exception:
        logger.debug("research_lab.catalog_inject_failed", exc_info=True)
        return list(candidates)


def gate_winner(
    *,
    champion: PolicyDNA | None,
    challenger: PolicyDNA,
    challenger_fitness: float,
    previous_fitness: float,
    sim_results: list[SimResult] | None,
    mode: str,
) -> tuple[PolicyDNA, float, dict[str, Any]]:
    if not research_lab_enabled(mode):
        return challenger, float(challenger_fitness), {"reason": "real_path_unchanged"}
    try:
        return apply_champion_challenger_gate(
            champion=champion,
            challenger=challenger,
            challenger_fitness=challenger_fitness,
            previous_fitness=previous_fitness,
            sim_results=sim_results,
        )
    except Exception:
        logger.exception("research_lab.champion_gate_failed")
        if champion is not None:
            return champion, float(previous_fitness), {
                "reason": "gate_error",
                "keep_champion": True,
                "promote_challenger": False,
            }
        return challenger, float(challenger_fitness), {"reason": "gate_error_no_champion"}
