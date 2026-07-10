"""Apply evolution candidate hyperparam mutations (typed risk contract)."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from lumina_core.agent_orchestration.schemas import RiskConfigMutationProposal
from lumina_core.engine.evolution_risk_proposal import apply_risk_config_mutation

if TYPE_CHECKING:
    from lumina_core.engine.meta_agent_core import SelfEvolutionMetaAgent


def apply_evolution_candidate(agent: "SelfEvolutionMetaAgent", candidate: dict[str, Any]) -> None:
    suggestion = dict(candidate.get("hyperparam_suggestion", {}))
    risk_keys = [k for k in ("max_risk_percent", "drawdown_kill_percent") if k in suggestion]
    if not risk_keys:
        return

    dna_hash = candidate.get("dna_hash") or candidate.get("hash")
    shadow_ref = (
        candidate.get("shadow_result_ref")
        or candidate.get("experiment_id")
        or candidate.get("shadow_experiment_id")
        or (candidate.get("ab_experiment") or {}).get("experiment_id")
    )
    decision_ctx = candidate.get("decision_context_id") or "nightly_evolution_risk_mutation"

    prop = RiskConfigMutationProposal(
        decision_context_id=str(decision_ctx),
        source="meta_agent_core._apply_candidate",
        dna_hash=str(dna_hash) if dna_hash else None,
        shadow_result_ref=str(shadow_ref) if shadow_ref else None,
        proposed_values={k: float(suggestion[k]) for k in risk_keys},
    )
    apply_risk_config_mutation(
        proposal=prop,
        engine=agent.engine,
        bus=getattr(agent.engine, "event_bus", None),
    )
