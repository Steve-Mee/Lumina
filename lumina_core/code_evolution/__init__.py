"""Trading code evolution — sandboxed, twin-gated, optional sandbox-store apply (H5).

Radical differentiator: Lumina may propose and safely *test* (and optionally *apply
to sandbox store*) small trading-related code/parameter changes. Hard rem:

- Default **disabled**
- Fixed operators only (parameter tweak / simple indicator / minor strategy snippet)
- **Approval Twin + constitution** before sandbox execution
- **Apply** only under H5 gates to ``state/code_evolution/applied/`` — never live repo / REAL
- Full audit + reversible journal under ``state/code_evolution/``

See ``docs/adr/0033-trading-code-evolution-prototype.md`` and ``docs/AGI_SAFETY.md``.
"""

from __future__ import annotations

from lumina_core.code_evolution.apply_gate import (
    ApplyEvidence,
    ApplyPolicy,
    CodeEvolutionApplyGate,
)
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
from lumina_core.code_evolution.runtime_overlay import (
    OverlaySnapshot,
    bind_overlay_to_engine,
    effective_min_confluence,
    empty_overlay,
    load_overlay,
)
from lumina_core.code_evolution.runtime_role import CHALLENGER, CHAMPION

__all__ = [
    "ALLOWED_TARGETS",
    "PARAMETER_CATALOG",
    "ApplyEvidence",
    "ApplyPolicy",
    "CodeEvolutionApplyGate",
    "CodeEvolutionConstitution",
    "CodeEvolutionController",
    "CodeEvolutionCycleResult",
    "CodeEvolutionPipeline",
    "CodeGuardResult",
    "CodeMutationOperator",
    "CodeMutationProposal",
    "CodeSandboxEvalResult",
    "OverlaySnapshot",
    "CHALLENGER",
    "CHAMPION",
    "default_param_snapshot",
    "effective_min_confluence",
    "empty_overlay",
    "bind_overlay_to_engine",
    "load_overlay",
    "run_code_evolution_dry_cycle",
]
