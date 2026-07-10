"""Regenerate generation_runner.py from orchestrator_core.py body."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "lumina_core" / "evolution" / "orchestrator_core.py"
OUT = ROOT / "lumina_core" / "evolution" / "generation_runner.py"

HEADER = '''"""Single-generation evolution cycle runner."""

from __future__ import annotations

import logging
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
from lumina_core.evolution.orchestrator_core import GenerationResult
from lumina_core.governance import SignedApproval

if TYPE_CHECKING:
    from lumina_core.evolution.orchestrator_core import EvolutionOrchestrator

logger = logging.getLogger(__name__)


def _compat() -> Any:
    from lumina_core.evolution import evolution_orchestrator as compat_module

    return compat_module


def run_single_generation(
    orchestrator: "EvolutionOrchestrator",
    *,
    generation_offset: int,
    mode: str,
    explicit_human_approval: bool,
    require_human_approval: bool,
    real_promotion_approvals: Sequence[SignedApproval] | None,
    base_metrics: dict[str, Any],
    sim_days: int,
) -> GenerationResult:
    top_dna, active_dna = resolve_initial_top_and_active_dna(
        orchestrator, base_metrics=base_metrics
    )
'''


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)
    body_lines = lines[403:848]

    prev_idx = next(i for i, line in enumerate(body_lines) if "previous_fitness" in line)
    body_lines = body_lines[prev_idx:]

    transformed: list[str] = []
    for line in body_lines:
        if line.startswith("        "):
            line = line[8:]  # method body (8 spaces) -> function body (0 extra before re-indent)
        line = line.replace("self.", "orchestrator.")
        line = line.replace("getattr(self,", "getattr(orchestrator,")
        transformed.append(("    " + line) if line.strip() else line)

    OUT.write_text(HEADER + "".join(transformed), encoding="utf-8")
    print(f"Wrote {OUT} ({len(OUT.read_text(encoding='utf-8').splitlines())} lines)")


if __name__ == "__main__":
    main()