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

logger = logging.getLogger(__name__)

Severity = Literal["fatal", "warn"]

# Hard physical limits — these cannot be overridden by config.
_MAX_RISK_PERCENT_REAL: Final[float] = 3.0
_MAX_DRAWDOWN_KILL_ANY: Final[float] = 25.0
_MAX_KELLY_FRACTION_REAL: Final[float] = 0.25
_MAX_LEVERAGE_REAL: Final[float] = 2.0
_MIN_BACKTEST_SHARPE_FOR_REAL: Final[float] = 0.3
_MAX_CONCENTRATION_PCT: Final[float] = 80.0
_MAX_DAILY_TRADE_FREQUENCY: Final[int] = 200
_DNA_INVALID_SENTINEL: Final[str] = "__dna_validation_error__"


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


def _mode_is_real(mode: str) -> bool:
    return str(mode).strip().lower() == "real"


def _mode_is_real_or_paper(mode: str) -> bool:
    return str(mode).strip().lower() in {"real", "paper"}


# ---------------------------------------------------------------------------
# Principle 0 — Structured DNA required
# ---------------------------------------------------------------------------


def _p0_structured_dna_required(content: dict[str, Any], mode: str) -> bool:
    """Any mode: DNA payload must be valid structured JSON object."""
    _ = mode
    return _DNA_INVALID_SENTINEL not in content


# ---------------------------------------------------------------------------
# Principle 1 — Capital Preservation (max risk per trade)
# ---------------------------------------------------------------------------


def _p1_capital_preservation(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: max_risk_percent must be ≤ 3 % (prevents account blowup)."""
    if not _mode_is_real(mode):
        return True
    hs = content.get("hyperparam_suggestion", {})
    if not isinstance(hs, dict):
        return True
    val = hs.get("max_risk_percent")
    if val is None:
        return True
    try:
        return float(val) <= _MAX_RISK_PERCENT_REAL
    except (TypeError, ValueError):
        return True


# ---------------------------------------------------------------------------
# Principle 2 — No Naked Orders (risk controller / gatekeeper must stay on)
# ---------------------------------------------------------------------------

_GATEKEEPER_BYPASS_KEYS: frozenset[str] = frozenset(
    {
        "disable_risk_controller",
        "bypass_order_gatekeeper",
        "skip_var_check",
        "no_capital_floor",
        "disable_hard_risk",
        "disable_kill_switch",
        "disable_position_limits",
        "no_gatekeeper",
    }
)


def _p2_no_naked_orders(content: dict[str, Any], mode: str) -> bool:
    """Any mode: DNA must never disable risk or order gatekeeper controls."""
    for key in _GATEKEEPER_BYPASS_KEYS:
        if content.get(key) is True:
            return False
    return True


# ---------------------------------------------------------------------------
# Principle 3 — Mutation Depth Constraint
# ---------------------------------------------------------------------------

_RADICAL_MUTATION_DEPTHS: frozenset[str] = frozenset(
    {
        "radical",
        "aggressive",
        "extreme",
        "unconstrained",
        "unrestricted",
    }
)


def _p3_mutation_depth(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: mutation_depth must be 'conservative' or 'moderate' — no radical changes."""
    if not _mode_is_real(mode):
        return True
    depth = str(content.get("mutation_depth", "conservative")).lower()
    return depth not in _RADICAL_MUTATION_DEPTHS


# ---------------------------------------------------------------------------
# Principle 4 — Human Approval Gate
# ---------------------------------------------------------------------------


def _p4_approval_required(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: approval gate cannot be explicitly disabled."""
    if not _mode_is_real(mode):
        return True
    if content.get("approval_required") is False:
        return False
    if content.get("skip_human_approval") is True:
        return False
    if content.get("auto_approve_real") is True:
        return False
    return True


# ---------------------------------------------------------------------------
# Principle 5 — Real Data Required for Neuroevolution
# ---------------------------------------------------------------------------


def _p5_real_data_for_neuro(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: neuroevolution must use real market data, not synthetic OHLC."""
    if not _mode_is_real(mode):
        return True
    neuro = content.get("neuroevolution", {})
    if isinstance(neuro, dict):
        if neuro.get("require_real_simulator_data") is False:
            return False
        if neuro.get("synthetic_only") is True:
            return False
    return True


# ---------------------------------------------------------------------------
# Principle 6 — Drawdown Kill Percent Bounded
# ---------------------------------------------------------------------------


def _p6_drawdown_kill_bounded(content: dict[str, Any], mode: str) -> bool:
    """Any mode: drawdown_kill_percent ≤ 25 % to prevent catastrophic losses."""
    hs = content.get("hyperparam_suggestion", {})
    if isinstance(hs, dict):
        val = hs.get("drawdown_kill_percent")
        if val is not None:
            try:
                if float(val) > _MAX_DRAWDOWN_KILL_ANY:
                    return False
            except (TypeError, ValueError):
                pass
    # Also check top-level key
    top_val = content.get("drawdown_kill_percent")
    if top_val is not None:
        try:
            if float(top_val) > _MAX_DRAWDOWN_KILL_ANY:
                return False
        except (TypeError, ValueError):
            pass
    return True


# ---------------------------------------------------------------------------
# Principle 7 — No Aggressive Evolution in REAL
# ---------------------------------------------------------------------------


def _p7_no_aggressive_evolution_real(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: aggressive_evolution mode is prohibited (too unstable for live capital)."""
    if not _mode_is_real(mode):
        return True
    if content.get("aggressive_evolution") is True:
        return False
    if str(content.get("evolution_mode", "")).lower() in {"aggressive", "radical", "extreme"}:
        return False
    return True


# ---------------------------------------------------------------------------
# Principle 8 — Kelly Fraction Cap
# ---------------------------------------------------------------------------


def _p8_kelly_fraction_cap(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: kelly_fraction must be ≤ 0.25 (full Kelly is provably ruinous)."""
    if not _mode_is_real(mode):
        return True
    kelly = content.get("kelly_fraction")
    if kelly is None:
        hs = content.get("hyperparam_suggestion", {})
        if isinstance(hs, dict):
            kelly = hs.get("kelly_fraction")
    if kelly is not None:
        try:
            if float(kelly) > _MAX_KELLY_FRACTION_REAL:
                return False
        except (TypeError, ValueError):
            pass
    return True


# ---------------------------------------------------------------------------
# Principle 9 — Daily Loss Hard Stop Required in REAL
# ---------------------------------------------------------------------------


def _p9_daily_loss_hard_stop(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: daily_loss_cap must NOT be explicitly disabled or set to 0/positive."""
    if not _mode_is_real(mode):
        return True
    hs = content.get("hyperparam_suggestion", {})
    if isinstance(hs, dict):
        cap = hs.get("daily_loss_cap")
        if cap is not None:
            try:
                # Cap must be negative (a loss limit) or absent; 0 or positive disables it.
                if float(cap) >= 0.0:
                    return False
            except (TypeError, ValueError):
                pass
    if content.get("disable_daily_loss_cap") is True:
        return False
    return True


# ---------------------------------------------------------------------------
# Principle 10 — Leverage Explosion Prevention
# ---------------------------------------------------------------------------


def _p10_no_leverage_explosion(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: leverage multiplier ≤ 2× — prevents catastrophic margin calls."""
    if not _mode_is_real(mode):
        return True
    lev = content.get("leverage_multiplier")
    if lev is None:
        hs = content.get("hyperparam_suggestion", {})
        if isinstance(hs, dict):
            lev = hs.get("leverage_multiplier")
    if lev is not None:
        try:
            if float(lev) > _MAX_LEVERAGE_REAL:
                return False
        except (TypeError, ValueError):
            pass
    return True


# ---------------------------------------------------------------------------
# Principle 11 — Minimum Backtest Quality Gate for REAL Promotion
# ---------------------------------------------------------------------------


def _p11_minimum_backtest_quality(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: backtest_sharpe_ratio must be ≥ 0.3 — rejects untested DNA."""
    if not _mode_is_real(mode):
        return True
    sharpe = content.get("backtest_sharpe_ratio")
    if sharpe is None:
        # If no backtest data is present, we do NOT block (DNA may not have
        # backtest metrics embedded yet — the orchestrator enforces this via
        # separate channels). Principle only fires when data IS present and bad.
        return True
    try:
        return float(sharpe) >= _MIN_BACKTEST_SHARPE_FOR_REAL
    except (TypeError, ValueError):
        return True


# ---------------------------------------------------------------------------
# Principle 12 — No Circuit Breaker Disable
# ---------------------------------------------------------------------------

_CIRCUIT_BREAKER_BYPASS_KEYS: frozenset[str] = frozenset(
    {
        "disable_circuit_breaker",
        "bypass_circuit_breaker",
        "no_circuit_breaker",
        "disable_emergency_halt",
        "skip_halt_check",
    }
)


def _p12_no_circuit_breaker_disable(content: dict[str, Any], mode: str) -> bool:
    """Any mode: the emergency circuit breaker can never be disabled by DNA."""
    for key in _CIRCUIT_BREAKER_BYPASS_KEYS:
        if content.get(key) is True:
            return False
    return True


# ---------------------------------------------------------------------------
# Principle 13 — No Session Guard Bypass in REAL
# ---------------------------------------------------------------------------

_SESSION_GUARD_BYPASS_KEYS: frozenset[str] = frozenset(
    {
        "bypass_session_guard",
        "disable_session_guard",
        "trade_outside_session",
        "ignore_session_window",
        "force_trade_closed",
    }
)


def _p13_no_session_guard_bypass(content: dict[str, Any], mode: str) -> bool:
    """REAL mode: session guard cannot be bypassed — prevents trading at bad times."""
    if not _mode_is_real(mode):
        return True
    for key in _SESSION_GUARD_BYPASS_KEYS:
        if content.get(key) is True:
            return False
    return True


# ---------------------------------------------------------------------------
# Principle 14 — Concentration Risk Limit (WARN)
# ---------------------------------------------------------------------------


def _p14_concentration_risk(content: dict[str, Any], mode: str) -> bool:
    """REAL/PAPER mode: single-instrument exposure ≤ 80 % of allocated capital (WARN)."""
    if not _mode_is_real_or_paper(mode):
        return True
    conc = content.get("single_instrument_exposure_pct")
    if conc is not None:
        try:
            if float(conc) > _MAX_CONCENTRATION_PCT:
                return False
        except (TypeError, ValueError):
            pass
    return True


# ---------------------------------------------------------------------------
# Principle 15 — Excessive Trade Frequency Guard (WARN)
# ---------------------------------------------------------------------------


def _p15_trade_frequency_guard(content: dict[str, Any], mode: str) -> bool:
    """Any mode: daily_trade_frequency_limit > 200 triggers a warning.

    HFT-style strategies risk exploding commissions and market impact costs.
    """
    freq = content.get("daily_trade_frequency_limit")
    if freq is not None:
        try:
            if int(freq) > _MAX_DAILY_TRADE_FREQUENCY:
                return False
        except (TypeError, ValueError):
            pass
    return True


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
