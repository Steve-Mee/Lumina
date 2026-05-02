"""Backward-compatible re-export for split self-evolution meta-agent modules."""

from __future__ import annotations

from .meta_agent import (
    SelfEvolutionMetaAgent,
    load_evolution_config,
    should_run_multi_gen_nightly,
)

__all__ = [
    "SelfEvolutionMetaAgent",
    "load_evolution_config",
    "should_run_multi_gen_nightly",
]
