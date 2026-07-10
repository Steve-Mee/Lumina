"""Mechanical split of meta_agent_core.py into evolution bounded modules (Fase 5A)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "lumina_core" / "engine" / "meta_agent_core.py"
EVO = ROOT / "lumina_core" / "evolution"

MUTATION_EXECUTOR = '''"""Apply evolution candidate hyperparam mutations (typed risk contract)."""

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
'''

DREAM_INTEGRATION_HEADER = '''"""Multi-generation dream / EvolutionOrchestrator nightly integration."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from lumina_bible.chroma_community import resolve_community_vector_collection
from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.evolution_orchestrator import EvolutionOrchestrator
from lumina_core.evolution.meta_agent_config import should_run_multi_gen_nightly

if TYPE_CHECKING:
    from lumina_core.engine.meta_agent_core import SelfEvolutionMetaAgent

'''


def _slice(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    # dream block from run_nightly_evolution (429-458)
    dream_body = _slice(lines, 429, 458)
    dream_body = (
        dream_body.replace("        if should_run_multi_gen_nightly(", "    if should_run_multi_gen_nightly(")
        .replace("            mutation_allowed=bool(mutation_allowed)", "        mutation_allowed=bool(mutation_allowed)")
        .replace("            dry_run=bool(dry_run)", "        dry_run=bool(dry_run)")
        .replace("            mode_key=str(mode_key)", "        mode_key=str(mode_key)")
        .replace("        ):", "    ):")
        .replace("            orchestrator", "        orchestrator")
        .replace("            _evo_cfg", "        _evo_cfg")
        .replace("            _ck", "        _ck")
        .replace("            sim_duration_hours", "        sim_duration_hours")
        .replace("            orch_result", "        orch_result")
        .replace("            outcome[\"multi_gen_cycle\"]", "        outcome[\"multi_gen_cycle\"]")
        .replace("            if self.obs_service", "        if agent.obs_service")
        .replace("                self.obs_service", "            agent.obs_service")
    )

    dream_fn = (
        DREAM_INTEGRATION_HEADER
        + "def run_multi_gen_nightly_cycle(\n"
        + "    agent: \"SelfEvolutionMetaAgent\",\n"
        + "    *,\n"
        + "    nightly_report: dict[str, Any],\n"
        + "    outcome: dict[str, Any],\n"
        + "    mode_key: str,\n"
        + "    mutation_allowed: bool,\n"
        + "    dry_run: bool,\n"
        + ") -> None:\n"
        + dream_body
    )
    (EVO / "dream_integration.py").write_text(dream_fn, encoding="utf-8")

    (EVO / "mutation_executor.py").write_text(MUTATION_EXECUTOR, encoding="utf-8")

    config_body = _slice(lines, 42, 49) + "\n\n" + _slice(lines, 1751, 1809)
    config_header = '''"""Meta-agent evolution configuration helpers."""

from __future__ import annotations

import os
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError

'''
    (EVO / "meta_agent_config.py").write_text(config_header + config_body, encoding="utf-8")

    nightly_header = '''"""Nightly self-evolution cycle orchestration."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from lumina_core.evolution.dream_integration import run_multi_gen_nightly_cycle
from lumina_core.evolution.multi_day_sim_runner import MultiDaySimRunner
from lumina_core.evolution.mutation_executor import apply_evolution_candidate
from lumina_core.evolution.simulator_data_support import enrich_nightly_report_simulator_data
from lumina_core.experiments.ab_framework import ABExperimentFramework

if TYPE_CHECKING:
    from lumina_core.engine.meta_agent_core import SelfEvolutionMetaAgent

logger = logging.getLogger(__name__)

'''

    nightly_body = _slice(lines, 167, 481)
    nightly_body = nightly_body.replace("        ", "    ", 1)  # unindent one level from method
    nightly_body = nightly_body.replace("self.", "agent.")
    nightly_body = nightly_body.replace(
        "            self._apply_candidate(best)",
        "            apply_evolution_candidate(agent, best)",
    )
    # Replace multi-gen block with dream integration call
    old_multi_gen = _slice(lines, 429, 458).replace("        ", "    ", 1).replace("self.", "agent.")
    nightly_body = nightly_body.replace(
        old_multi_gen,
        "    run_multi_gen_nightly_cycle(\n"
        "        agent,\n"
        "        nightly_report=nightly_report,\n"
        "        outcome=outcome,\n"
        "        mode_key=str(mode_key),\n"
        "        mutation_allowed=bool(mutation_allowed),\n"
        "        dry_run=bool(dry_run),\n"
        "    )\n",
    )

    nightly_fn = (
        nightly_header
        + "def run_nightly_evolution_cycle(\n"
        + "    agent: \"SelfEvolutionMetaAgent\",\n"
        + "    *,\n"
        + "    nightly_report: dict[str, Any],\n"
        + "    dry_run: bool = False,\n"
        + ") -> dict[str, Any]:\n"
        + nightly_body
    )
    (EVO / "nightly_cycle.py").write_text(nightly_fn, encoding="utf-8")

    # Rebuild slim meta_agent_core.py
    imports = _slice(lines, 1, 40)
    imports = imports.replace(
        "from ..evolution.simulator_data_support import enrich_nightly_report_simulator_data\n",
        "",
    ).replace(
        "from ..evolution.evolution_orchestrator import EvolutionOrchestrator\n",
        "",
    ).replace(
        "from lumina_bible.chroma_community import resolve_community_vector_collection\n",
        "",
    ).replace(
        "from ..config_loader import ConfigLoader\n",
        "",
    ).replace(
        "from ..evolution.genetic_operators import calculate_fitness, crossover, mutate_prompt\n",
        "",
    ).replace(
        "from ..evolution.meta_swarm import MetaSwarm, meta_swarm_governance_enabled, parallel_realities_from_config\n",
        "",
    ).replace(
        "from lumina_core.experiments.ab_framework import ABExperimentFramework\n",
        "",
    ).replace(
        "from ..evolution.multi_day_sim_runner import MultiDaySimRunner\n",
        "",
    ).replace(
        "from lumina_core.engine.evolution_risk_proposal import apply_risk_config_mutation\n",
        "",
    ).replace(
        "from lumina_core.agent_orchestration.schemas import (\n    TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,\n    RiskConfigMutationProposal,\n    TradingEngineExecutionAggregate,\n    typed_payload_from_event,\n)",
        "from lumina_core.agent_orchestration.schemas import (\n    TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,\n    TradingEngineExecutionAggregate,\n    typed_payload_from_event,\n)",
    )
    imports += (
        "from lumina_core.evolution.meta_agent_config import load_evolution_config, should_run_multi_gen_nightly\n"
        "from lumina_core.evolution.mutation_executor import apply_evolution_candidate\n"
        "from lumina_core.evolution.nightly_cycle import run_nightly_evolution_cycle\n\n"
    )

    class_header = _slice(lines, 52, 165)
    run_delegate = (
        "    def run_nightly_evolution(self, *, nightly_report: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:\n"
        "        return run_nightly_evolution_cycle(self, nightly_report=nightly_report, dry_run=dry_run)\n\n"
    )

    keep_methods = (
        _slice(lines, 483, 521)
        + _slice(lines, 560, 631)
        + _slice(lines, 690, 763)
        + _slice(lines, 1020, 1048)
        + "    def _apply_candidate(self, candidate: dict[str, Any]) -> None:\n"
        + "        apply_evolution_candidate(self, candidate)\n\n"
        + _slice(lines, 1089, 1121)
        + _slice(lines, 1545, 1748)
    )

    load_cfg = ""  # moved to meta_agent_config, re-exported via import

    slim = imports + class_header + run_delegate + keep_methods
    SRC.write_text(slim, encoding="utf-8")
    print(f"Wrote evolution modules + slim meta_agent_core ({len(slim.splitlines())} lines)")


if __name__ == "__main__":
    main()