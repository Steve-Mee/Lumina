"""CodeEvolutionConstitution — fail-closed principles for trading-code proposals.

Complements TradingConstitution / ConstitutionalGuard. Does not replace them.
v1 evaluates only inside sandbox; never auths live capital-path edits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.code_evolution.operators import (
    FORBIDDEN_PARAMETER_KEYS,
    PARAMETER_CATALOG,
    validate_parameter_tweak,
)
from lumina_core.code_evolution.proposal import (
    ALLOWED_TARGETS,
    FORBIDDEN_TARGET_PREFIXES,
    CodeMutationOperator,
    CodeMutationProposal,
)
from lumina_core.safety.trading_constitution import ConstitutionalViolation

_MAX_ESTIMATED_LOC = 40
_MAX_SNIPPET_CHARS = 4000


@dataclass(slots=True)
class CodeGuardResult:
    """Result of a code-evolution constitutional check."""

    passed: bool
    violations: list[ConstitutionalViolation]
    check_phase: str
    mode: str
    proposal_id: str = ""

    @property
    def fatal_violations(self) -> list[ConstitutionalViolation]:
        return [v for v in self.violations if v.severity == "fatal"]

    @property
    def violation_names(self) -> list[str]:
        return [v.principle_name for v in self.violations]


@dataclass(slots=True)
class CodeEvolutionConstitution:
    """Machine-enforceable rules for code evolution proposals."""

    max_estimated_loc: int = _MAX_ESTIMATED_LOC
    max_snippet_chars: int = _MAX_SNIPPET_CHARS

    def check_pre_mutation(
        self, proposal: CodeMutationProposal, *, mode: str = "sim"
    ) -> CodeGuardResult:
        violations: list[ConstitutionalViolation] = []

        def fatal(name: str, description: str, detail: str = "") -> None:
            violations.append(
                ConstitutionalViolation(
                    principle_name=name,
                    description=description,
                    severity="fatal",
                    detail=detail or description,
                    mode=mode,
                )
            )

        op = proposal.operator
        if not isinstance(op, CodeMutationOperator):
            try:
                op = CodeMutationOperator(str(op))
            except ValueError:
                fatal("whitelisted_operator", "Unknown operator", str(proposal.operator))
                return CodeGuardResult(
                    passed=False,
                    violations=violations,
                    check_phase="pre_mutation",
                    mode=mode,
                    proposal_id=proposal.proposal_id,
                )

        target = str(proposal.target or "").replace("\\", "/")
        if target not in ALLOWED_TARGETS:
            fatal("whitelisted_target", "Target not in sandbox allowlist", target)

        for prefix in FORBIDDEN_TARGET_PREFIXES:
            if prefix in target or target.startswith(prefix):
                fatal("no_risk_path_touch", "Forbidden path/target", f"{target} matched {prefix}")

        if int(proposal.estimated_loc or 0) > self.max_estimated_loc:
            fatal(
                "small_change_only",
                "Estimated LOC exceeds v1 limit",
                f"{proposal.estimated_loc} > {self.max_estimated_loc}",
            )

        # Full-file / multi-file forbidden signals
        payload = proposal.payload or {}
        code = str(payload.get("code") or "")
        if len(code) > self.max_snippet_chars:
            fatal("no_full_file", "Snippet too large for v1", str(len(code)))
        if "\nclass " in code or code.strip().startswith("class "):
            fatal("no_full_file", "Class definitions not allowed in v1 snippets")

        # Operator-specific
        if op == CodeMutationOperator.PARAMETER_TWEAK:
            key = str(payload.get("key") or "")
            if key in FORBIDDEN_PARAMETER_KEYS:
                fatal("no_risk_path_touch", "Risk parameter key forbidden", key)
            try:
                old_v = float(payload.get("old_value"))
                new_v = float(payload.get("new_value"))
            except (TypeError, ValueError):
                fatal("bounds_respected", "Parameter values must be numeric")
            else:
                for name in validate_parameter_tweak(key, old_v, new_v):
                    fatal(name, f"Parameter tweak rejected: {name}", key)
            if target != "sandbox.params":
                fatal("whitelisted_target", "PARAMETER_TWEAK requires sandbox.params", target)

        elif op == CodeMutationOperator.ADD_SIMPLE_INDICATOR:
            if target != "sandbox.indicator":
                fatal("whitelisted_target", "ADD_SIMPLE_INDICATOR requires sandbox.indicator", target)
            if "def indicator" not in code:
                fatal("requires_sandbox", "Indicator must define indicator(series)", "missing_entrypoint")
            if "import " in code or "open(" in code or "exec(" in code or "eval(" in code:
                fatal("no_risk_path_touch", "Unsafe tokens in indicator code")

        elif op == CodeMutationOperator.STRATEGY_SNIPPET_ADJUST:
            if target != "sandbox.strategy_snippet":
                fatal(
                    "whitelisted_target",
                    "STRATEGY_SNIPPET_ADJUST requires sandbox.strategy_snippet",
                    target,
                )
            if "def generated_strategy" not in code:
                fatal("requires_sandbox", "Snippet must define generated_strategy", "missing_entrypoint")
            if "import " in code or "open(" in code or "exec(" in code or "eval(" in code:
                fatal("no_risk_path_touch", "Unsafe tokens in strategy snippet")

        # Reversibility artifact required (before snapshot present for param tweaks)
        if op == CodeMutationOperator.PARAMETER_TWEAK and not proposal.before_snapshot:
            fatal("reversible_artifact", "before_snapshot required for reversible param tweak")

        # Mode honesty: REAL still allowed to evaluate in sandbox, never apply (pipeline enforces)
        passed = len([v for v in violations if v.severity == "fatal"]) == 0
        return CodeGuardResult(
            passed=passed,
            violations=violations,
            check_phase="pre_mutation",
            mode=mode,
            proposal_id=proposal.proposal_id,
        )

    def check_pre_promotion(
        self, proposal: CodeMutationProposal, *, mode: str = "sim"
    ) -> CodeGuardResult:
        """v1 never promotes to live tree — always fail-closed on apply intent."""
        base = self.check_pre_mutation(proposal, mode=mode)
        if not base.passed:
            return CodeGuardResult(
                passed=False,
                violations=base.violations,
                check_phase="pre_promotion",
                mode=mode,
                proposal_id=proposal.proposal_id,
            )
        # Explicit evaluate-only gate
        block = ConstitutionalViolation(
            principle_name="v1_evaluate_only",
            description="Code evolution v1 forbids live apply/promotion",
            severity="fatal",
            detail="applied=False always in v1",
            mode=mode,
        )
        return CodeGuardResult(
            passed=False,
            violations=[block],
            check_phase="pre_promotion",
            mode=mode,
            proposal_id=proposal.proposal_id,
        )

    def dna_proxy_for_guard(self, proposal: CodeMutationProposal) -> str:
        """Serialize a conservative DNA-shaped string for ConstitutionalGuard screening.

        Parameter tweaks that accidentally include risk keys will be visible to
        TradingConstitution; pure indicator snippets stay non-trading-shaped.
        """
        import json

        payload = proposal.payload or {}
        content: dict[str, Any] = {
            "code_evolution": True,
            "operator": proposal.operator.value
            if isinstance(proposal.operator, CodeMutationOperator)
            else str(proposal.operator),
            "target": proposal.target,
            "proposal_id": proposal.proposal_id,
        }
        if proposal.operator == CodeMutationOperator.PARAMETER_TWEAK:
            key = str(payload.get("key") or "")
            # Only attach as hyperparam_suggestion for non-risk keys
            if key and key not in FORBIDDEN_PARAMETER_KEYS and key in PARAMETER_CATALOG:
                content["hyperparam_suggestion"] = {
                    key: payload.get("new_value"),
                }
            elif key in FORBIDDEN_PARAMETER_KEYS:
                content["max_risk_percent"] = payload.get("new_value")
        return json.dumps(content, sort_keys=True)
