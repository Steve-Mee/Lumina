"""Typed proposal models for sandboxed trading code evolution (v1).

Evaluate-only: proposals never auto-apply to the live tree or REAL paths.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CodeMutationOperator(str, Enum):
    """Fixed, narrow operators only — never full-file rewrites."""

    PARAMETER_TWEAK = "parameter_tweak"
    ADD_SIMPLE_INDICATOR = "add_simple_indicator"
    STRATEGY_SNIPPET_ADJUST = "strategy_snippet_adjust"


# Logical sandbox targets only (not live repo paths).
ALLOWED_TARGETS: frozenset[str] = frozenset(
    {
        "sandbox.params",
        "sandbox.indicator",
        "sandbox.strategy_snippet",
    }
)

# Prefixes that must never appear as targets or in snippet/path hints.
FORBIDDEN_TARGET_PREFIXES: tuple[str, ...] = (
    "lumina_core/risk/",
    "lumina_core/broker/",
    "lumina_core/safety/trading_constitution",
    "lumina_core/risk/final_arbitration",
    "order_gatekeeper",
    "promotion_gate",
)


@dataclass(frozen=True, slots=True)
class CodeMutationProposal:
    """A single small, reviewable trading-code mutation proposal."""

    proposal_id: str
    operator: CodeMutationOperator
    target: str
    description: str
    payload: dict[str, Any]
    rationale: str
    estimated_loc: int
    before_snapshot: dict[str, Any] = field(default_factory=dict)
    after_snapshot: dict[str, Any] = field(default_factory=dict)
    constitution_passed: bool = False
    twin_recommendation: bool = False
    twin_effective: bool = False
    sandbox_passed: bool = False
    decision_context_id: str = ""
    created_by: str = "code_evolution_controller"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["operator"] = self.operator.value
        return d


@dataclass(slots=True)
class CodeSandboxEvalResult:
    """Result of sandboxed evaluation of a code proposal."""

    proposal_id: str
    passed: bool
    score: float
    violations: list[str]
    input_hash: str
    output_hash: str
    timed_out: bool = False
    error: str = ""
    sandbox_used: bool = True
    mode: str = "sim"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CodeEvolutionCycleResult:
    """Outcome of one dry / gated evolution cycle."""

    enabled: bool
    proposals: list[CodeMutationProposal]
    decisions: list[dict[str, Any]]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "proposals": [p.to_dict() for p in self.proposals],
            "decisions": list(self.decisions),
            "metrics": dict(self.metrics),
        }
