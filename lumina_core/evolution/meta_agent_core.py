"""Evolution meta-agent facade (engine core + config helpers)."""

from __future__ import annotations

from lumina_core.engine.meta_agent_core import SelfEvolutionMetaAgent
from lumina_core.evolution.meta_agent_config import load_evolution_config, should_run_multi_gen_nightly

__all__ = [
    "SelfEvolutionMetaAgent",
    "load_evolution_config",
    "should_run_multi_gen_nightly",
]
