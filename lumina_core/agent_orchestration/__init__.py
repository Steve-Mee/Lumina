"""Bounded context: agent_orchestration.

Uses lazy attribute resolution to avoid import cycles during engine bootstrap.
"""

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus

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


def __getattr__(name: str):
    if name in {"AgentBlackboard", "BlackboardEvent"}:
        from lumina_core.engine.agent_blackboard import AgentBlackboard, BlackboardEvent

        return {"AgentBlackboard": AgentBlackboard, "BlackboardEvent": BlackboardEvent}[name]
    if name == "AgentPolicyGateway":
        from lumina_core.engine.agent_policy_gateway import AgentPolicyGateway

        return AgentPolicyGateway
    if name == "MetaAgentOrchestrator":
        from lumina_core.engine.meta_agent_orchestrator import MetaAgentOrchestrator

        return MetaAgentOrchestrator
    if name == "ReasoningService":
        from lumina_core.engine.reasoning_service import ReasoningService

        return ReasoningService
    if name == "SelfEvolutionMetaAgent":
        from lumina_core.engine.self_evolution_meta_agent import SelfEvolutionMetaAgent

        return SelfEvolutionMetaAgent
    if name == "SwarmManager":
        from lumina_core.engine.swarm_manager import SwarmManager

        return SwarmManager
    raise AttributeError(name)
