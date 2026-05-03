"""Backward-compatible export for the split self-evolution meta-agent core."""

from __future__ import annotations

from lumina_core.evolution.meta_agent_core import SelfEvolutionMetaAgent, load_evolution_config, should_run_multi_gen_nightly

__all__ = [
    "SelfEvolutionMetaAgent",
    "load_evolution_config",
    "should_run_multi_gen_nightly",
]
