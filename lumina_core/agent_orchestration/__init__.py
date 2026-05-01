"""Bounded context: agent_orchestration.

Uses lazy attribute resolution to avoid import cycles during engine bootstrap.
Resolved lazy names are stored on this module after first access so repeated lookups
do not re-import or re-execute ``__getattr__`` (standard PEP 562 lazy-export pattern).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus

if TYPE_CHECKING:
    # Static-only imports: satisfies Pyright/__all__ without eager runtime imports (cycles).
    from lumina_core.engine.agent_blackboard import AgentBlackboard, BlackboardEvent
    from lumina_core.engine.agent_policy_gateway import AgentPolicyGateway
    from lumina_core.engine.meta_agent_orchestrator import MetaAgentOrchestrator
    from lumina_core.engine.reasoning_service import ReasoningService
    from lumina_core.engine.self_evolution_meta_agent import SelfEvolutionMetaAgent
    from lumina_core.engine.swarm_manager import SwarmManager

__all__ = [
    "AgentBlackboard",
    "BlackboardEvent",
    "AgentPolicyGateway",
    "MetaAgentOrchestrator",
    "ReasoningService",
    "SelfEvolutionMetaAgent",
    "SwarmManager",
    "DomainEvent",
    "EventBus",
]

# (importlib module path, attribute name) — single table for extension and review.
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "AgentBlackboard": ("lumina_core.engine.agent_blackboard", "AgentBlackboard"),
    "BlackboardEvent": ("lumina_core.engine.agent_blackboard", "BlackboardEvent"),
    "AgentPolicyGateway": ("lumina_core.engine.agent_policy_gateway", "AgentPolicyGateway"),
    "MetaAgentOrchestrator": ("lumina_core.engine.meta_agent_orchestrator", "MetaAgentOrchestrator"),
    "ReasoningService": ("lumina_core.engine.reasoning_service", "ReasoningService"),
    "SelfEvolutionMetaAgent": ("lumina_core.engine.self_evolution_meta_agent", "SelfEvolutionMetaAgent"),
    "SwarmManager": ("lumina_core.engine.swarm_manager", "SwarmManager"),
}


def __getattr__(name: str) -> Any:
    spec = _LAZY_EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_path, attr_name = spec
    module = importlib.import_module(mod_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
