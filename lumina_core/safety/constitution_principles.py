"""Constitutional principle checkers (_p0…_p15).

Behavior-preserving extract from trading_constitution. ZERO semantic changes.
"""

from __future__ import annotations

from typing import Any, Final


# Hard physical limits — these cannot be overridden by config.
_MAX_RISK_PERCENT_REAL: Final[float] = 3.0
_MAX_DRAWDOWN_KILL_ANY: Final[float] = 25.0
_MAX_KELLY_FRACTION_REAL: Final[float] = 0.25
_MAX_LEVERAGE_REAL: Final[float] = 2.0
_MIN_BACKTEST_SHARPE_FOR_REAL: Final[float] = 0.3
_MAX_CONCENTRATION_PCT: Final[float] = 80.0
_MAX_DAILY_TRADE_FREQUENCY: Final[int] = 200
_DNA_INVALID_SENTINEL: Final[str] = "__dna_validation_error__"


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

