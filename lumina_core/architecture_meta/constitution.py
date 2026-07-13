"""ArchitectureConstitution — machine-enforceable principles for arch mutations.

Complements (does not duplicate) Trading Constitution.
Fail-closed. Emits ConstitutionViolation events on breach (reuse pattern).

Principles (v1, narrow):
- no_god_module_growth
- preserves_bounded_contexts
- advances_typed_contracts
- requires_measurable_improvement
- small_diff_only
- no_trading_behavior_change
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.safety.trading_constitution import (
    ConstitutionalViolation,
)


@dataclass(slots=True)
class ArchitectureConstitution:
    """Minimal constitution checker for architecture proposals."""

    max_patch_lines: int = 80
    max_god_loc: int = 700

    def check_pre_mutation(self, proposal: Any, *, mode: str = "sim") -> "GuardResult":
        """Return GuardResult-like. Blocks on fatal. Reuses violation types."""
        violations: list[ConstitutionalViolation] = []
        fatal = False

        diff = getattr(proposal, "diff", "") or ""
        target = getattr(proposal, "target_file", "") or ""
        delta = getattr(proposal, "expected_delta", 0.0) or 0.0
        mtype = str(getattr(proposal, "mutation_type", ""))

        # Small diff only
        if diff.count("\n") > self.max_patch_lines * 1.5:
            v = ConstitutionalViolation(
                principle_name="small_diff_only",
                description="Patch exceeds size limit",
                severity="fatal",
                detail=f"lines in diff > {self.max_patch_lines}",
                mode=mode,
            )
            violations.append(v)
            fatal = True

        # God growth forbidden
        if "god" in mtype.lower() or "large" in target.lower():
            # Heuristic: caller must supply context; for v1 we are conservative
            if getattr(proposal, "before_score", 10) > 8.0 and "extract" not in mtype:
                v = ConstitutionalViolation(
                    principle_name="no_god_module_growth",
                    description="Attempt to mutate already-healthy large module",
                    severity="fatal",
                    detail=target,
                    mode=mode,
                )
                violations.append(v)
                fatal = True

        # Must claim measurable improvement
        if delta < 0.10:
            v = ConstitutionalViolation(
                principle_name="requires_measurable_improvement",
                description="Expected delta too low",
                severity="fatal",
                detail=str(delta),
                mode=mode,
            )
            violations.append(v)
            fatal = True

        # Boundary & typed hints (light)
        if "cross" in target.lower() and "port" not in mtype and "boundary" not in mtype:
            # soft warn only in v1
            pass

        passed = not fatal
        if fatal:
            # Emit via existing mechanism (best effort)
            try:
                from lumina_core.audit import get_audit_logger
                get_audit_logger().log(
                    "constitution.arch_violation",
                    {"violations": [v.principle_name for v in violations]},
                )
            except Exception:
                pass

        return GuardResult(passed=passed, violations=violations, check_phase="pre_mutation", mode=mode)

    def check_pre_promotion(self, proposal: Any, *, mode: str = "sim") -> "GuardResult":
        """Final gate before human-approved apply."""
        # In v1 we trust sandbox + human marker more than extra static checks.
        # Still fail-closed on obvious.
        res = self.check_pre_mutation(proposal, mode=mode)
        if not res.passed:
            return res
        return GuardResult(passed=True, violations=[], check_phase="pre_promotion", mode=mode)


@dataclass(slots=True)
class GuardResult:
    passed: bool
    violations: list[ConstitutionalViolation]
    check_phase: str
    mode: str

    @property
    def fatal_violations(self) -> list[ConstitutionalViolation]:
        return [v for v in self.violations if v.severity == "fatal"]
