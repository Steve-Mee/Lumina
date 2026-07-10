"""Mechanical split of orchestrator_core.py (Fase 5B)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "lumina_core" / "evolution" / "orchestrator_core.py"
EVO = ROOT / "lumina_core" / "evolution"

BIRTH_GEN0_BOOTSTRAP = '''"""Birth gen0 DNA resolution and active-DNA bootstrap for evolution cycles."""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from lumina_core.birth.dna_handoff import resolve_birth_gen0_dna
from lumina_core.evolution.dna_registry import PolicyDNA
from lumina_core.evolution.mutation_pipeline import MutationPipeline

if TYPE_CHECKING:
    from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator

logger = logging.getLogger(__name__)


def resolve_initial_top_and_active_dna(
    orchestrator: "EvolutionOrchestrator",
    *,
    base_metrics: dict[str, Any],
) -> tuple[list[PolicyDNA], PolicyDNA | None]:
    top_dna = orchestrator._registry.get_ranked_dna(limit=3)
    active_dna = orchestrator._registry.get_latest_dna(version="active")
    if not top_dna and active_dna is None:
        birth_dna = resolve_birth_gen0_dna(orchestrator._registry)
        if birth_dna is not None:
            active_dna = birth_dna
            top_dna = [birth_dna]
        else:
            active_dna = orchestrator._bootstrap_active_dna(base_metrics=base_metrics)
            top_dna = [active_dna]
    return top_dna, active_dna


def bootstrap_active_dna(
    orchestrator: "EvolutionOrchestrator",
    *,
    base_metrics: dict[str, Any],
) -> PolicyDNA:
    orchestrator._mutation_pipeline = MutationPipeline(
        registry=orchestrator._registry,
        constitutional_guard=orchestrator._constitutional_guard,
        logger=logger,
    )
    return orchestrator._mutation_pipeline.bootstrap_active_dna(base_metrics=base_metrics)
'''

GENERATION_RUNNER_HEADER = '''"""Single-generation evolution cycle runner."""

from __future__ import annotations

from typing import Any, Sequence, TYPE_CHECKING

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.evolution.birth_gen0_bootstrap import resolve_initial_top_and_active_dna
from lumina_core.evolution.dream_engine import enrich_nightly_report_with_dream
from lumina_core.evolution.fitness_evaluator import (
    resolve_parallel_realities_count as _resolve_parallel_realities_count,
    seed_from_hash as _seed_from_hash,
    utcnow as _utcnow,
)
from lumina_core.evolution.meta_swarm import meta_swarm_governance_enabled
from lumina_core.evolution.multi_day_sim_runner import MultiDaySimRunner
from lumina_core.governance import SignedApproval

if TYPE_CHECKING:
    from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator, GenerationResult


def _compat() -> Any:
    from lumina_core.evolution import evolution_orchestrator as compat_module

    return compat_module


'''


def _slice(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def _transform_run_single_generation(body: str) -> str:
    body = body.replace("        top_dna = self._registry.get_ranked_dna(limit=3)\n", "")
    body = body.replace(
        "        active_dna = self._registry.get_latest_dna(version=\"active\")\n", ""
    )
    birth_block = (
        "        if not top_dna and active_dna is None:\n"
        "            birth_dna = resolve_birth_gen0_dna(self._registry)\n"
        "            if birth_dna is not None:\n"
        "                active_dna = birth_dna\n"
        "                top_dna = [birth_dna]\n"
        "            else:\n"
        "                active_dna = self._bootstrap_active_dna(base_metrics=base_metrics)\n"
        "                top_dna = [active_dna]\n"
    )
    body = body.replace(birth_block, "")
    insert = (
        "    top_dna, active_dna = resolve_initial_top_and_active_dna(\n"
        "        orchestrator, base_metrics=base_metrics\n"
        "    )\n"
    )
    # After function signature closing paren line
    marker = "    ) -> GenerationResult:\n"
    if marker not in body:
        raise RuntimeError("run_single_generation signature marker not found")
    body = body.replace(marker, marker + insert, 1)
    body = body.replace("self.", "orchestrator.")
    body = body.replace("def _run_single_generation(", "def run_single_generation(\n    orchestrator: \"EvolutionOrchestrator\",\n    *,\n")
    # Fix duplicate orchestrator in first param block - the transform may have broken signature
    return body


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)
    run_body = _slice(lines, 393, 848)
    run_body = _transform_run_single_generation(run_body)
    # Add return type import at runtime to avoid circular import at module load
    run_footer = (
        "\n\n# Late import for GenerationResult (orchestrator_core delegates here).\n"
        "from lumina_core.evolution.orchestrator_core import GenerationResult  # noqa: E402\n"
    )
    gen_runner = GENERATION_RUNNER_HEADER + run_body
    if "from lumina_core.evolution.orchestrator_core import GenerationResult" not in gen_runner:
        gen_runner = gen_runner.replace(
            "def run_single_generation(",
            "from lumina_core.evolution.orchestrator_core import GenerationResult\n\n\ndef run_single_generation(",
            1,
        )

    (EVO / "birth_gen0_bootstrap.py").write_text(BIRTH_GEN0_BOOTSTRAP, encoding="utf-8")
    (EVO / "generation_runner.py").write_text(gen_runner, encoding="utf-8")
    print("Wrote birth_gen0_bootstrap.py and generation_runner.py")


if __name__ == "__main__":
    main()