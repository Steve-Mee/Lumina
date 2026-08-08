"""T4: REAL / capital-risk broker reconciliation readiness gate (fail-closed config).

Does not start brokers or arm capital. Operators use this before REAL mode switch
and CI uses it in dry-run packs.
"""

from __future__ import annotations

from typing import Any

from lumina_core.engine.mode_capabilities import resolve_mode_capabilities

# Modes where missing fill reconciliation is a safety defect (not optional).
_RECON_REQUIRED_MODES = frozenset({"real", "sim_real_guard", "live", "production", "prod"})

__all__ = [
    "evaluate_real_broker_recon_gate",
    "recon_required_for_mode",
]


def recon_required_for_mode(mode: str | None) -> bool:
    m = str(mode or "").strip().lower()
    if m in _RECON_REQUIRED_MODES:
        return True
    try:
        caps = resolve_mode_capabilities(m)
        return bool(caps.capital_at_risk) or bool(caps.reconcile_fills_enabled_default)
    except ValueError:
        return False


def evaluate_real_broker_recon_gate(
    *,
    trade_mode: str | None,
    reconcile_fills: bool,
    reconciliation_method: str | None = "websocket",
    reconciliation_timeout_seconds: float | int | None = 15.0,
    live_broker_configured: bool | None = None,
    ninjatrader_enabled: bool | None = None,
) -> dict[str, Any]:
    """Config-level gate for REAL broker fill reconciliation.

    Fail-closed when capital-risk modes disable recon or use invalid timeouts.
    """
    mode = str(trade_mode or "paper").strip().lower() or "paper"
    method = str(reconciliation_method or "websocket").strip().lower() or "websocket"
    try:
        timeout = float(reconciliation_timeout_seconds if reconciliation_timeout_seconds is not None else 15.0)
    except (TypeError, ValueError):
        timeout = 0.0

    required = recon_required_for_mode(mode)
    failures: list[str] = []

    if required and not bool(reconcile_fills):
        failures.append("reconcile_fills_disabled_in_capital_risk_mode")
    if required and method not in {"websocket", "polling"}:
        failures.append(f"invalid_reconciliation_method:{method}")
    if required and timeout < 5.0:
        failures.append(f"reconciliation_timeout_too_low:{timeout}")
    if required and live_broker_configured is False:
        failures.append("live_broker_not_configured")
    if required and ninjatrader_enabled is False and mode in {"real", "live", "production", "prod"}:
        # NT may be optional if CrossTrade — only flag when explicitly disabled with real
        failures.append("ninjatrader_disabled_in_real_mode")

    ok = len(failures) == 0
    return {
        "schema": "real_broker_recon_gate_v1",
        "ok": ok,
        "trade_mode": mode,
        "recon_required": required,
        "reconcile_fills": bool(reconcile_fills),
        "reconciliation_method": method,
        "reconciliation_timeout_seconds": timeout,
        "failures": failures,
        "policy": {
            "timeout_without_fill": "observability_only_no_economic_ledger",
            "economic_pnl_source": "broker_confirmed_fill_only",
            "never_arms_real": True,
        },
        "message": (
            "REAL/sim_real_guard recon config OK"
            if ok
            else "REAL recon config fail-closed: " + "; ".join(failures)
        ),
        "runbook": "docs/trade-fill-reconciliation-runbook.md",
    }
