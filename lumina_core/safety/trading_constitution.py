"""Trading Constitution — the machine-readable Noordster of LUMINA's AGI Safety.

Every DNA mutation that could affect live trading MUST pass every FATAL
principle defined here before being executed, sandboxed, or promoted.

Design principles:
  - Fail-closed: a check that raises is treated as a violation, not ignored.
  - Immutable at runtime: principles cannot be modified after process start.
  - Layered: FATAL violations block immediately; WARN violations are logged and
    surfaced in the audit trail but do not block execution.
  - Mode-aware: REAL mode has the strictest set of rules; SIM/PAPER allow
    experimentation within physical bounds only.

Capital preservation is SACRED.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Final, Literal

from lumina_core.safety.constitution_principles import (
    _DNA_INVALID_SENTINEL,
    _MAX_CONCENTRATION_PCT,
    _MAX_DAILY_TRADE_FREQUENCY,
    _MAX_DRAWDOWN_KILL_ANY,
    _MAX_KELLY_FRACTION_REAL,
    _MAX_LEVERAGE_REAL,
    _MAX_RISK_PERCENT_REAL,
    _MIN_BACKTEST_SHARPE_FOR_REAL,
    _p0_structured_dna_required,
    _p1_capital_preservation,
    _p2_no_naked_orders,
    _p3_mutation_depth,
    _p4_approval_required,
    _p5_real_data_for_neuro,
    _p6_drawdown_kill_bounded,
    _p7_no_aggressive_evolution_real,
    _p8_kelly_fraction_cap,
    _p9_daily_loss_hard_stop,
    _p10_no_leverage_explosion,
    _p11_minimum_backtest_quality,
    _p12_no_circuit_breaker_disable,
    _p13_no_session_guard_bypass,
    _p14_concentration_risk,
    _p15_trade_frequency_guard,
)

logger = logging.getLogger(__name__)

Severity = Literal["fatal", "warn"]

# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstitutionalPrinciple:
    """A single named, immutable constitutional principle with a runtime check.

    The ``check_fn`` receives the *parsed* DNA content as a ``dict`` and the
    trading mode string.  It returns ``True`` when the principle is SATISFIED
    (no violation) and ``False`` when violated.  The function must never raise;
    exceptions are caught by the auditor and treated as violations.
    """

    name: str
    description: str
    severity: Severity
    rationale: str
    check_fn: Callable[[dict[str, Any], str], bool]


@dataclass(frozen=True, slots=True)
class ConstitutionalViolation:
    """Records a single principle violation detected during an audit."""

    principle_name: str
    description: str
    severity: Severity
    detail: str = ""
    mode: str = ""


class ConstitutionalViolationError(Exception):
    """Raised when one or more FATAL constitutional violations are detected.

    Attributes:
        violations: All violations that triggered the error (only fatals).
    """

    def __init__(self, violations: list[ConstitutionalViolation]) -> None:
        self.violations = violations
        names = [v.principle_name for v in violations if v.severity == "fatal"]
        super().__init__(f"FATAL constitutional violation(s) — DNA blocked: {names}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_dna_content(raw: str) -> dict[str, Any]:
    """Parse and minimally validate raw DNA content.

    Returns a dict on success. When input is invalid, returns a dict containing
    ``_DNA_INVALID_SENTINEL`` with a human-readable reason so principle checks
    can fail closed.
    """
    if not raw or not isinstance(raw, str):
        return {_DNA_INVALID_SENTINEL: "empty_or_non_string"}
    stripped = raw.strip()
    if not stripped.startswith("{"):
        return {_DNA_INVALID_SENTINEL: "non_json_payload"}
    try:
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            return {_DNA_INVALID_SENTINEL: "json_not_object"}
        if not parsed:
            return {_DNA_INVALID_SENTINEL: "empty_json_object"}
        hs = parsed.get("hyperparam_suggestion")
        if hs is not None and not isinstance(hs, dict):
            return {_DNA_INVALID_SENTINEL: "hyperparam_suggestion_not_dict"}
        return parsed
    except (json.JSONDecodeError, TypeError, ValueError):
        return {_DNA_INVALID_SENTINEL: "json_parse_error"}


# ---------------------------------------------------------------------------
# Constitution registry
# ---------------------------------------------------------------------------

_PRINCIPLES: list[ConstitutionalPrinciple] = [
    ConstitutionalPrinciple(
        name="dna_must_be_structured_json",
        description="DNA payload must be valid, non-empty JSON object with supported schema",
        severity="fatal",
        rationale="Plain-text or malformed DNA bypasses machine-enforced safety checks and is therefore blocked.",
        check_fn=_p0_structured_dna_required,
    ),
    ConstitutionalPrinciple(
        name="capital_preservation_in_real",
        description=f"max_risk_percent must be ≤ {_MAX_RISK_PERCENT_REAL}% in REAL mode",
        severity="fatal",
        rationale="Capital preservation is the Noordster. Risking > 3% per trade in live mode is existentially reckless.",
        check_fn=_p1_capital_preservation,
    ),
    ConstitutionalPrinciple(
        name="no_naked_orders",
        description="DNA must not disable risk controller, order gatekeeper, or position limits",
        severity="fatal",
        rationale="Risk controls are not optional. Disabling them exposes the account to unlimited loss.",
        check_fn=_p2_no_naked_orders,
    ),
    ConstitutionalPrinciple(
        name="max_mutation_depth_enforced",
        description="mutation_depth must be 'conservative' or 'moderate' in REAL mode — radical forbidden",
        severity="fatal",
        rationale="Radical DNA changes in live trading are like performing surgery while sprinting. Conservative mutations allow measurable A/B comparison.",
        check_fn=_p3_mutation_depth,
    ),
    ConstitutionalPrinciple(
        name="approval_required_in_real",
        description="Human approval gate must not be bypassed in REAL mode",
        severity="fatal",
        rationale="AGI systems handling real capital require a human in the loop for major decisions. This is non-negotiable.",
        check_fn=_p4_approval_required,
    ),
    ConstitutionalPrinciple(
        name="no_synthetic_data_in_real_neuro",
        description="Neuroevolution in REAL mode must use real market OHLC data",
        severity="fatal",
        rationale="Models trained on synthetic data develop a reality gap. Live capital cannot be risked on strategies optimised for fictional markets.",
        check_fn=_p5_real_data_for_neuro,
    ),
    ConstitutionalPrinciple(
        name="drawdown_kill_percent_bounded",
        description=f"drawdown_kill_percent must be ≤ {_MAX_DRAWDOWN_KILL_ANY}% in any mode",
        severity="fatal",
        rationale="A drawdown kill > 25% means the system will eat > 1/4 of the account before stopping. This is catastrophic risk.",
        check_fn=_p6_drawdown_kill_bounded,
    ),
    ConstitutionalPrinciple(
        name="no_aggressive_evolution_in_real",
        description="aggressive_evolution mode is forbidden in REAL mode",
        severity="fatal",
        rationale="Aggressive evolution in live trading is the equivalent of changing the engine of a flying plane. SIM is the lab; REAL is production.",
        check_fn=_p7_no_aggressive_evolution_real,
    ),
    ConstitutionalPrinciple(
        name="kelly_fraction_cap",
        description=f"kelly_fraction must be ≤ {_MAX_KELLY_FRACTION_REAL} in REAL mode",
        severity="fatal",
        rationale="Full Kelly criterion is optimal in theory and catastrophic in practice due to estimation error. Quarter-Kelly is the institutional standard.",
        check_fn=_p8_kelly_fraction_cap,
    ),
    ConstitutionalPrinciple(
        name="daily_loss_hard_stop_required",
        description="daily_loss_cap must be negative (active) in REAL mode — disabling it is forbidden",
        severity="fatal",
        rationale="A day without a loss cap is a day that can wipe the account. Every professional trading desk has one.",
        check_fn=_p9_daily_loss_hard_stop,
    ),
    ConstitutionalPrinciple(
        name="no_leverage_explosion",
        description=f"leverage_multiplier must be ≤ {_MAX_LEVERAGE_REAL}× in REAL mode",
        severity="fatal",
        rationale="High leverage in futures trading compounds losses exponentially. 2× maximum is already aggressive; beyond that is gambling.",
        check_fn=_p10_no_leverage_explosion,
    ),
    ConstitutionalPrinciple(
        name="minimum_backtest_quality_for_real",
        description=f"backtest_sharpe_ratio (when present) must be ≥ {_MIN_BACKTEST_SHARPE_FOR_REAL} for REAL promotion",
        severity="fatal",
        rationale="Promoting an untested or negatively-tested strategy to live trading is scientific malpractice.",
        check_fn=_p11_minimum_backtest_quality,
    ),
    ConstitutionalPrinciple(
        name="no_circuit_breaker_disable",
        description="Emergency circuit breaker / halt mechanism must never be disabled by DNA",
        severity="fatal",
        rationale="The circuit breaker is the last line of defence against runaway execution. Disabling it removes the ability to stop in an emergency.",
        check_fn=_p12_no_circuit_breaker_disable,
    ),
    ConstitutionalPrinciple(
        name="no_session_guard_bypass",
        description="Trading session guard must not be bypassed in REAL mode",
        severity="fatal",
        rationale="Trading outside defined session windows risks positions in illiquid hours where spreads explode and circuit-breakers can gap through stops.",
        check_fn=_p13_no_session_guard_bypass,
    ),
    ConstitutionalPrinciple(
        name="concentration_risk_limit",
        description=f"Single-instrument exposure must be ≤ {_MAX_CONCENTRATION_PCT}% of allocated capital",
        severity="warn",
        rationale="Over-concentration in one instrument eliminates diversification benefits and amplifies idiosyncratic risk.",
        check_fn=_p14_concentration_risk,
    ),
    ConstitutionalPrinciple(
        name="trade_frequency_guard",
        description=f"daily_trade_frequency_limit should not exceed {_MAX_DAILY_TRADE_FREQUENCY} trades/day",
        severity="warn",
        rationale="Excessive trading frequency generates commission drag and market-impact costs that erode edge. HFT strategies require specialised infrastructure.",
        check_fn=_p15_trade_frequency_guard,
    ),
]


class TradingConstitution:
    """The complete, immutable set of constitutional trading principles.

    This is the single source of truth for all AGI safety checks.  It is
    instantiated once as ``TRADING_CONSTITUTION`` and shared across all
    subsystems.

    Usage::

        violations = TRADING_CONSTITUTION.audit(dna_content, mode="real")
        fatal = [v for v in violations if v.severity == "fatal"]
        if fatal:
            raise ConstitutionalViolationError(fatal)

    Thread-safety: read-only after construction; safe for concurrent audits.
    """

    def __init__(
        self,
        principles: list[ConstitutionalPrinciple] | None = None,
    ) -> None:
        self._principles: tuple[ConstitutionalPrinciple, ...] = tuple(
            principles if principles is not None else _PRINCIPLES
        )

    @property
    def principles(self) -> tuple[ConstitutionalPrinciple, ...]:
        """Immutable sequence of all registered principles."""
        return self._principles

    @property
    def fatal_count(self) -> int:
        return sum(1 for p in self._principles if p.severity == "fatal")

    @property
    def warn_count(self) -> int:
        return sum(1 for p in self._principles if p.severity == "warn")

    def audit(
        self,
        dna_content: str,
        mode: str,
        *,
        raise_on_fatal: bool = True,
    ) -> list[ConstitutionalViolation]:
        """Audit *dna_content* against every principle for *mode*.

        Args:
            dna_content: Raw DNA string (JSON or plain text).
            mode: Trading mode — ``"real"``, ``"paper"``, or ``"sim"``.
            raise_on_fatal: If ``True``, raises ``ConstitutionalViolationError``
                when any FATAL violation is detected.

        Returns:
            Full list of violations (FATAL + WARN).  Empty means all clear.

        Raises:
            ConstitutionalViolationError: When ``raise_on_fatal=True`` and at
                least one FATAL violation is detected.
        """
        parsed = _parse_dna_content(dna_content)
        mode_str = str(mode).strip().lower()
        violations: list[ConstitutionalViolation] = []

        for principle in self._principles:
            try:
                satisfied = principle.check_fn(parsed, mode_str)
            except Exception as exc:
                # Fail-closed: any check that crashes counts as a FATAL violation.
                logger.error(
                    "Constitutional check %r raised unexpectedly (fail-closed): %s",
                    principle.name,
                    exc,
                )
                satisfied = False

            if not satisfied:
                v = ConstitutionalViolation(
                    principle_name=principle.name,
                    description=principle.description,
                    severity=principle.severity,
                    detail=f"mode={mode_str}",
                    mode=mode_str,
                )
                violations.append(v)
                log = logger.error if v.severity == "fatal" else logger.warning
                log(
                    "Constitution %s — %s [mode=%s]",
                    v.severity.upper(),
                    v.principle_name,
                    mode_str,
                )

        if raise_on_fatal:
            fatals = [v for v in violations if v.severity == "fatal"]
            if fatals:
                raise ConstitutionalViolationError(fatals)

        return violations

    def is_clean(self, dna_content: str, mode: str) -> bool:
        """Return ``True`` if DNA passes all FATAL principles for *mode*."""
        try:
            self.audit(dna_content, mode=mode, raise_on_fatal=True)
            return True
        except ConstitutionalViolationError:
            return False

    def probe_attack(
        self,
        dna_content: str,
        mode: str,
        *,
        expected_violations: list[str],
    ) -> dict[str, Any]:
        """Red-team probe: verify that a crafted attack DNA triggers expected violations.

        Returns a dict with ``blocked``, ``expected_hit``, ``violations`` and
        ``missed_violations`` for use in red-team test assertions.
        """
        violations = self.audit(dna_content, mode=mode, raise_on_fatal=False)
        found_names = {v.principle_name for v in violations}
        expected_set = set(expected_violations)
        return {
            "blocked": bool(any(v.severity == "fatal" for v in violations)),
            "violations": [v.principle_name for v in violations],
            "expected_hit": expected_set <= found_names,
            "missed_violations": list(expected_set - found_names),
        }


# Singleton — import this instance across all subsystems.
TRADING_CONSTITUTION: Final[TradingConstitution] = TradingConstitution()
