"""Backward-compatible export for the split self-evolution meta-agent core."""

from __future__ import annotations

from lumina_core.engine.evolution_config import load_evolution_config, should_run_multi_gen_nightly
from lumina_core.engine.meta_agent_core import SelfEvolutionMetaAgent

__all__ = [
    "SelfEvolutionMetaAgent",
    "load_evolution_config",
    "should_run_multi_gen_nightly",
]
