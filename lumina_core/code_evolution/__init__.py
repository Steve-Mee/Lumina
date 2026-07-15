"""Trading code evolution (v1) — sandboxed, twin-gated, evaluate-only.

Radical differentiator: Lumina may propose and safely *test* small trading-related
code/parameter changes inside a strict sandbox. Hard rem:

- Default **disabled**
- Fixed operators only (parameter tweak / simple indicator / minor strategy snippet)
- **Approval Twin + constitution** before sandbox execution
- **Never** mutates live repo / REAL capital paths in v1
- Full audit + reversible journal under ``state/code_evolution/``

See ``docs/adr/0033-trading-code-evolution-prototype.md`` and ``docs/AGI_SAFETY.md``.
"""

from __future__ import annotations

from lumina_core.code_evolution.constitution import (
    CodeEvolutionConstitution,
    CodeGuardResult,
)
from lumina_core.code_evolution.operators import (
    PARAMETER_CATALOG,
    CodeEvolutionController,
    default_param_snapshot,
)
from lumina_core.code_evolution.pipeline import (
    CodeEvolutionPipeline,
    run_code_evolution_dry_cycle,
)
from lumina_core.code_evolution.proposal import (
    ALLOWED_TARGETS,
    CodeEvolutionCycleResult,
    CodeMutationOperator,
    CodeMutationProposal,
    CodeSandboxEvalResult,
)

__all__ = [
    "ALLOWED_TARGETS",
    "PARAMETER_CATALOG",
    "CodeEvolutionConstitution",
    "CodeEvolutionController",
    "CodeEvolutionCycleResult",
    "CodeEvolutionPipeline",
    "CodeGuardResult",
    "CodeMutationOperator",
    "CodeMutationProposal",
    "CodeSandboxEvalResult",
    "default_param_snapshot",
    "run_code_evolution_dry_cycle",
]
