"""Bounded context: Agents — emotional twin, meta-orchestrator, swarm coordination.

Re-exports from canonical engine-level modules (ADR-002 migration pending).

Current members:
    EmotionalTwinAgent    — psychological bias correction agent
    MetaAgentOrchestrator — nightly reflection and hyperparameter proposal
    SwarmManager          — multi-symbol swarm coordination (compatibility wrapper)
"""

from __future__ import annotations

from lumina_core.engine.emotional_twin_agent import EmotionalTwinAgent
from lumina_core.engine.meta_agent_orchestrator import MetaAgentOrchestrator
from lumina_core.engine.swarm_manager import SwarmManager

__all__ = [
    "EmotionalTwinAgent",
    "MetaAgentOrchestrator",
    "SwarmManager",
]
