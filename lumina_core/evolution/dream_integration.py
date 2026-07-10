"""Multi-generation dream / EvolutionOrchestrator nightly integration."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

import lumina_core.engine.meta_agent_core as _meta_facade
from lumina_core.config_loader import ConfigLoader

if TYPE_CHECKING:
    from lumina_core.engine.meta_agent_core import SelfEvolutionMetaAgent

def run_multi_gen_nightly_cycle(
    agent: "SelfEvolutionMetaAgent",
    *,
    nightly_report: dict[str, Any],
    outcome: dict[str, Any],
    mode_key: str,
    mutation_allowed: bool,
    dry_run: bool,
) -> None:
    if _meta_facade.should_run_multi_gen_nightly(
        mutation_allowed=bool(mutation_allowed), dry_run=bool(dry_run), mode_key=str(mode_key)
    ):
        orchestrator = _meta_facade.EvolutionOrchestrator()
        orchestrator.bind_promotion_event_bus(getattr(agent.engine, "event_bus", None))
        orchestrator.bind_market_data_service(getattr(agent.engine, "market_data_service", None))
        orchestrator.bind_ppo_trainer(agent.ppo_trainer)
        _evo_cfg = ConfigLoader.section("evolution", default={}) or {}
        _ck = _evo_cfg.get("community_knowledge") if isinstance(_evo_cfg, dict) else None
        orchestrator.bind_vector_collection(
            _meta_facade.resolve_community_vector_collection(
                agent.engine,
                community_cfg=_ck if isinstance(_ck, dict) else None,
            )
        )
        sim_duration_hours = int(nightly_report.get("sim_duration_hours", 24) or 24)
        orch_result = orchestrator.run_nightly_evolution_cycle(
            generations=3,
            sim_duration_hours=sim_duration_hours,
            nightly_report=nightly_report,
            blackboard=agent.blackboard,
            mode=mode_key,
        )
        outcome["multi_gen_cycle"] = orch_result
        if agent.obs_service is not None:
            agent.obs_service.record_evolution_proposal(
                    status=f"multi_gen:{orch_result.get('status', 'unknown')}",
                    confidence=float(outcome.get("proposal", {}).get("confidence", 0.0) or 0.0),
                    best_candidate=str(outcome.get("best_candidate", {}).get("name", "unknown")),
                )
