"""Agent, evolution, and swarm service wiring."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from lumina_agents.news_agent import NewsAgent
from lumina_core.agent_orchestration import AgentBlackboard, MetaAgentOrchestrator, SelfEvolutionMetaAgent
from lumina_core.engine.canonical_training import InfiniteSimulator, PPOTrainer
from lumina_core.engine.emotional_twin_agent import EmotionalTwinAgent
from lumina_core.engine.swarm_manager import SwarmManager
from lumina_core.evolution.meta_agent_config import load_evolution_config

if TYPE_CHECKING:
    from lumina_core.container import ApplicationContainer


def _blackboard_flags() -> tuple[bool, bool, bool]:
    blackboard_enabled = os.getenv("LUMINA_BLACKBOARD_ENABLED", "true").strip().lower() == "true"
    blackboard_enforced = os.getenv("LUMINA_BLACKBOARD_ENFORCED", "false").strip().lower() == "true"
    orchestrator_enabled = os.getenv("LUMINA_META_ORCHESTRATOR_ENABLED", "true").strip().lower() == "true"
    return blackboard_enabled, blackboard_enforced, orchestrator_enabled


def prepare_blackboard(container: "ApplicationContainer") -> None:
    blackboard_enabled, blackboard_enforced, _ = _blackboard_flags()
    if blackboard_enforced and not blackboard_enabled:
        raise RuntimeError("LUMINA_BLACKBOARD_ENFORCED=true requires LUMINA_BLACKBOARD_ENABLED=true")

    if blackboard_enabled:
        container.blackboard = AgentBlackboard(obs_service=container.observability_service)
        container.blackboard.load_recent_from_disk()
        container.engine.bind_blackboard(container.blackboard)
    else:
        container.blackboard = None  # type: ignore[assignment]


def wire_intelligence_agents(container: "ApplicationContainer") -> None:
    """News/PPO trainers, simulators, and meta-evolution stack."""
    container.news_agent = NewsAgent(engine=container.engine)
    container.ppo_trainer = PPOTrainer(engine=container.engine)
    container.engine.ppo_trainer = container.ppo_trainer

    container.emotional_twin_agent = EmotionalTwinAgent(engine=container.engine)
    container.engine.emotional_twin_agent = container.emotional_twin_agent
    container.infinite_simulator = InfiniteSimulator(
        runtime=container.runtime_context,
        market_data_service=container.market_data_service,
        ppo_trainer=container.ppo_trainer,
    )
    container.engine.infinite_simulator = container.infinite_simulator

    evolution_cfg = load_evolution_config()
    container.self_evolution_meta_agent = SelfEvolutionMetaAgent.from_container(
        container=container,
        enabled=bool(evolution_cfg.get("enabled", True)),
        approval_required=bool(evolution_cfg.get("approval_required", True)),
        mode=str(evolution_cfg.get("mode", getattr(container.config, "trade_mode", "real"))),
        aggressive_evolution=bool(evolution_cfg.get("aggressive_evolution", False)),
        max_mutation_depth=str(evolution_cfg.get("max_mutation_depth", "conservative")),
        obs_service=container.observability_service,
        fine_tuning_cfg=evolution_cfg.get("fine_tuning", {}),
    )
    container.self_evolution_meta_agent.blackboard = container.blackboard

    _, _, orchestrator_enabled = _blackboard_flags()
    if orchestrator_enabled and container.blackboard is not None:
        container.meta_agent_orchestrator = MetaAgentOrchestrator(
            blackboard=container.blackboard,
            self_evolution_agent=container.self_evolution_meta_agent,
            event_bus=container.event_bus,
            ppo_trainer=container.ppo_trainer,
            bible_engine=container.engine.bible_engine,
        )
        container.engine.meta_agent_orchestrator = container.meta_agent_orchestrator
    else:
        container.meta_agent_orchestrator = None  # type: ignore[assignment]
        container.engine.meta_agent_orchestrator = None

    try:
        from lumina_core.evolution.challenger_venue.attach import attach_challenger_surfaces

        attach_challenger_surfaces(container.engine, workspace=".")
    except Exception:
        import logging

        logging.getLogger(__name__).exception("challenger_surfaces.attach_failed")


def wire_swarm(container: "ApplicationContainer") -> None:
    container.swarm_manager = SwarmManager(container.engine)
    container.engine.swarm = container.swarm_manager


def bind_evolution_promotion_event_bus(container: "ApplicationContainer") -> None:
    from lumina_core.evolution.evolution_orchestrator import EvolutionOrchestrator
    from lumina_core.runtime.runtime_twin_oversight import RuntimeTwinOversight

    orchestrator = EvolutionOrchestrator()
    orchestrator.bind_promotion_event_bus(container.event_bus)
    orchestrator.bind_market_data_service(container.market_data_service)

    # RuntimeTwinOversight subscribes to evolution.twin.decision for autonomy telemetry.
    # Twin itself binds via orchestrator.bind_promotion_event_bus → ApprovalTwinAgent.bind_event_bus.
    mode = "sim"
    try:
        cfg_mode = getattr(getattr(container, "config", None), "mode", None) or getattr(
            getattr(container, "engine", None), "mode", None
        )
        if cfg_mode:
            mode = str(cfg_mode)
    except Exception:
        mode = "sim"
    try:
        RuntimeTwinOversight.get().bind(container.event_bus, mode=mode)
    except Exception:
        # Observability only — never block container bootstrap.
        pass