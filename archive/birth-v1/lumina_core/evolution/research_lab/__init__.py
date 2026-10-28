"""Strategy Research Lab — catalog seeds + champion-challenger on truthful fitness."""
from __future__ import annotations

from lumina_core.evolution.research_lab.catalog import CATALOG_SEEDS, inject_catalog_challengers
from lumina_core.evolution.research_lab.champion_challenger import (
    apply_champion_challenger_gate,
    champion_challenger_decision,
)
from lumina_core.evolution.research_lab.cycle import (
    gate_winner,
    merge_catalog_challengers,
    research_lab_enabled,
)

__all__ = [
    "CATALOG_SEEDS",
    "inject_catalog_challengers",
    "champion_challenger_decision",
    "apply_champion_challenger_gate",
    "gate_winner",
    "merge_catalog_challengers",
    "research_lab_enabled",
]
