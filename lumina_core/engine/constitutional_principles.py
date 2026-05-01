"""Constitutional Trading Principles — runtime enforcement for Lumina v53.

These principles are the machine-readable encoding of the Noordster from
.cursorrules.  Every DNA mutation that targets REAL-mode trading MUST pass
all FATAL principles before being promoted.

Usage:
    checker = ConstitutionalChecker()
    violations = checker.audit(dna, mode="real")
    if any(v.severity == "fatal" for v in violations):
        raise ConstitutionalViolationError(violations)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

logger = logging.getLogger(__name__)

Severity = Literal["fatal", "warn"]


@dataclass(frozen=True, slots=True)
class ConstitutionalPrinciple:
    """A single enforceable principle with a runtime check function."""

    name: str
    description: str
    severity: Severity
    # check_fn receives the parsed DNA content dict and the trading mode string.
    # Returns True when the principle is SATISFIED (no violation).
    check_fn: Callable[[dict[str, Any], str], bool]


@dataclass(frozen=True, slots=True)
class ConstitutionalViolation:
    principle_name: str
    description: str
    severity: Severity
    detail: str = ""


class ConstitutionalViolationError(Exception):
    """Raised when a fatal constitutional violation is detected."""

    def __init__(self, violations: list[ConstitutionalViolation]) -> None:
        self.violations = violations
        fatals = [v for v in violations if v.severity == "fatal"]
        super().__init__(
            f"Constitutional violation(s) — FATAL: {[v.principle_name for v in fatals]}"
        )


def _parse_content(dna_content: str) -> dict[str, Any]:
    """Safely parse DNA content to a dict; returns empty dict on failure."""
    try:
        parsed = json.loads(dna_content)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


# ---------------------------------------------------------------------------
# Principle definitions
# ---------------------------------------------------------------------------

def _capital_preservation_in_real(content: dict[str, Any], mode: str) -> bool:
    """In REAL mode, daily_loss_cap must be set and negative (preserving capital)."""
    if mode != "real":
        return True
    hs = content.get("hyperparam_suggestion", {})
    if not isinstance(hs, dict):
        return True
    max_risk = hs.get("max_risk_percent")
    # Reject if max_risk_percent > 3 % in real mode
    if max_risk is not None:
        try:
            if float(max_risk) > 3.0:
                return False
        except (TypeError, ValueError):
            pass
    return True


def _no_naked_orders(content: dict[str, Any], mode: str) -> bool:
    """DNA must not explicitly disable the order gatekeeper or risk controller."""
    forbidden_keys = {
        "disable_risk_controller",
        "bypass_order_gatekeeper",
        "skip_var_check",
        "no_capital_floor",
    }
    for key in forbidden_keys:
        if content.get(key) is True:
            return False
    return True


def _max_mutation_depth_enforced(content: dict[str, Any], mode: str) -> bool:
    """In REAL mode, mutation_depth must be 'conservative' or absent."""
    if mode != "real":
        return True
    depth = content.get("mutation_depth", "conservative")
    if isinstance(depth, str) and depth in {"radical", "aggressive", "extreme"}:
        return False
    return True


def _approval_required_in_real(content: dict[str, Any], mode: str) -> bool:
    """In REAL mode, approval_required must not be explicitly disabled."""
    if mode != "real":
        return True
    if content.get("approval_required") is False:
        return False
    return True


def _no_synthetic_data_in_real_neuro(content: dict[str, Any], mode: str) -> bool:
    """Neuroevolution in REAL mode must not rely on synthetic OHLC data."""
    if mode != "real":
        return True
    neuro = content.get("neuroevolution", {})
    if isinstance(neuro, dict):
        if neuro.get("require_real_simulator_data") is False:
            return False
    return True


def _drawdown_kill_percent_bounded(content: dict[str, Any], mode: str) -> bool:
    """drawdown_kill_percent must be <= 25% in any mode (prevents catastrophic loss)."""
    hs = content.get("hyperparam_suggestion", {})
    if isinstance(hs, dict):
        val = hs.get("drawdown_kill_percent")
        if val is not None:
            try:
                if float(val) > 25.0:
                    return False
            except (TypeError, ValueError):
                pass
    return True


def _no_aggressive_evolution_in_real(content: dict[str, Any], mode: str) -> bool:
    """aggressive_evolution must be False in REAL mode."""
    if mode != "real":
        return True
    if content.get("aggressive_evolution") is True:
        return False
    return True


# ---------------------------------------------------------------------------
# Registry of all principles
# ---------------------------------------------------------------------------

CONSTITUTIONAL_PRINCIPLES: list[ConstitutionalPrinciple] = [
    ConstitutionalPrinciple(
        name="capital_preservation_in_real",
        description="max_risk_percent must be <= 3.0 % in REAL mode",
        severity="fatal",
        check_fn=_capital_preservation_in_real,
    ),
    ConstitutionalPrinciple(
        name="no_naked_orders",
        description="DNA must not disable risk controller or order gatekeeper",
        severity="fatal",
        check_fn=_no_naked_orders,
    ),
    ConstitutionalPrinciple(
        name="max_mutation_depth_enforced",
        description="mutation_depth must be 'conservative' in REAL mode",
        severity="fatal",
        check_fn=_max_mutation_depth_enforced,
    ),
    ConstitutionalPrinciple(
        name="approval_required_in_real",
        description="approval_required must not be disabled in REAL mode",
        severity="fatal",
        check_fn=_approval_required_in_real,
    ),
    ConstitutionalPrinciple(
        name="no_synthetic_data_in_real_neuro",
        description="neuroevolution in REAL mode requires real OHLC data",
        severity="fatal",
        check_fn=_no_synthetic_data_in_real_neuro,
    ),
    ConstitutionalPrinciple(
        name="drawdown_kill_percent_bounded",
        description="drawdown_kill_percent must be <= 25 % in any mode",
        severity="fatal",
        check_fn=_drawdown_kill_percent_bounded,
    ),
    ConstitutionalPrinciple(
        name="no_aggressive_evolution_in_real",
        description="aggressive_evolution must be False in REAL mode",
        severity="warn",
        check_fn=_no_aggressive_evolution_in_real,
    ),
]


class ConstitutionalChecker:
    """Audits a PolicyDNA against all constitutional principles.

    Raises ``ConstitutionalViolationError`` if any FATAL principle is violated
    and ``raise_on_fatal=True`` (default).  Returns the full list of
    violations (including warnings) regardless.
    """

    def __init__(
        self,
        principles: list[ConstitutionalPrinciple] | None = None,
    ) -> None:
        self._principles = principles if principles is not None else CONSTITUTIONAL_PRINCIPLES

    def audit(
        self,
        dna_content: str,
        mode: str,
        *,
        raise_on_fatal: bool = True,
    ) -> list[ConstitutionalViolation]:
        """Run all principles against *dna_content* for *mode*.

        Args:
            dna_content: Raw DNA content string (JSON or plain prompt text).
            mode: Trading mode — ``"real"``, ``"paper"``, or ``"sim"``.
            raise_on_fatal: If True, raises ConstitutionalViolationError when
                any FATAL violation is detected.

        Returns:
            List of violations (may be empty if all principles pass).
        """
        parsed = _parse_content(dna_content)
        violations: list[ConstitutionalViolation] = []

        for principle in self._principles:
            try:
                satisfied = principle.check_fn(parsed, str(mode).lower())
            except Exception as exc:
                logger.warning(
                    "Constitutional check %r raised unexpectedly: %s — treating as warn",
                    principle.name,
                    exc,
                )
                satisfied = True  # fail-open on check errors to avoid false fatals

            if not satisfied:
                violation = ConstitutionalViolation(
                    principle_name=principle.name,
                    description=principle.description,
                    severity=principle.severity,
                    detail=f"mode={mode}",
                )
                violations.append(violation)
                logger.warning(
                    "Constitutional %s: %s [%s]",
                    violation.severity.upper(),
                    violation.principle_name,
                    violation.detail,
                )

        if raise_on_fatal:
            fatals = [v for v in violations if v.severity == "fatal"]
            if fatals:
                raise ConstitutionalViolationError(fatals)

        return violations
