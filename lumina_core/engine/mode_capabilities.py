from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModeCapabilities:
    requires_live_broker: bool
    risk_enforced: bool
    session_guard_enforced: bool
    eod_force_close_enabled: bool
    reconcile_fills_enabled_default: bool
    is_learning_mode: bool
    capital_at_risk: bool
    account_mode_hint: str


_MODES: dict[str, ModeCapabilities] = {
    "paper": ModeCapabilities(
        requires_live_broker=False,
        risk_enforced=False,
        session_guard_enforced=False,
        eod_force_close_enabled=False,
        reconcile_fills_enabled_default=False,
        is_learning_mode=False,
        capital_at_risk=False,
        account_mode_hint="paper",
    ),
    "sim": ModeCapabilities(
        requires_live_broker=True,
        risk_enforced=False,
        session_guard_enforced=True,
        eod_force_close_enabled=False,
        reconcile_fills_enabled_default=False,
        is_learning_mode=True,
        capital_at_risk=False,
        account_mode_hint="sim",
    ),
    "sim_real_guard": ModeCapabilities(
        requires_live_broker=True,
        risk_enforced=True,
        session_guard_enforced=True,
        eod_force_close_enabled=True,
        reconcile_fills_enabled_default=True,
        is_learning_mode=False,
        capital_at_risk=False,
        account_mode_hint="sim",
    ),
    "real": ModeCapabilities(
        requires_live_broker=True,
        risk_enforced=True,
        session_guard_enforced=True,
        eod_force_close_enabled=True,
        reconcile_fills_enabled_default=True,
        is_learning_mode=False,
        capital_at_risk=True,
        account_mode_hint="real",
    ),
}


def resolve_mode_capabilities(mode: str) -> ModeCapabilities:
    normalized = str(mode or "").strip().lower()
    if normalized not in _MODES:
        raise ValueError(f"Unsupported trade mode: {mode}")
    return _MODES[normalized]
