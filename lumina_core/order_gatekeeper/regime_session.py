"""Regime snapshot and session/broker gate helpers."""

from __future__ import annotations

from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.order_gatekeeper.engine_helpers import safe_log_warning

def session_guard_allows_trading(engine: Any) -> tuple[bool, str]:
    """Centralized SessionGuard enforcement status used across runtime gates."""
    risk_controller = getattr(engine, "risk_controller", None)
    limits = getattr(risk_controller, "_active_limits", None)
    enforce_session_guard = bool(getattr(limits, "enforce_session_guard", True))
    if not enforce_session_guard:
        return True, "session_guard_disabled"

    session_guard = getattr(engine, "session_guard", None)
    if session_guard is None:
        return False, "session_guard_unavailable"

    if session_guard.is_rollover_window():
        return False, "rollover_window"
    if not session_guard.is_trading_session():
        return False, "outside_trading_session"

    return True, "ok"


def broker_metadata_contract_allowed(engine: Any, symbol: str) -> tuple[bool, str]:
    """Optional broker metadata check; pass-through when broker does not expose metadata APIs."""
    container = getattr(engine, "container", None)
    if container is None:
        app = getattr(engine, "app", None)
        container = getattr(app, "container", None)
    broker = getattr(container, "broker", None) if container is not None else None
    if broker is None:
        return True, "broker_unavailable_for_metadata"

    # Preferred explicit capability.
    if hasattr(broker, "is_contract_tradeable"):
        ok, reason = broker.is_contract_tradeable(str(symbol))
        return bool(ok), str(reason or "broker_metadata_gate")

    # Optional metadata dictionary capability.
    if hasattr(broker, "get_contract_metadata"):
        meta = broker.get_contract_metadata(str(symbol))
        if isinstance(meta, dict):
            if bool(meta.get("expired", False)):
                return False, "broker_metadata_expired"
            if meta.get("tradeable") is False:
                return False, "broker_metadata_not_tradeable"

    return True, "ok"


def audit_stale_override(engine: Any, symbol: str, mode: str) -> None:
    safe_log_warning(
        engine,
        (f"OVERRIDE_AUDIT,gate=stale_contract,mode={mode},symbol={symbol},source=LUMINA_ALLOW_STALE_CONTRACTS"),
    )


def resolve_regime_snapshot(engine: Any, regime: str | None = None) -> dict[str, Any]:
    """Resolve and refresh the active regime snapshot used by risk/session gates."""
    reasoning_service = getattr(engine, "reasoning_service", None)
    if reasoning_service is None or not hasattr(reasoning_service, "refresh_regime_snapshot"):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="REGIME_SNAPSHOT_PROVIDER_MISSING",
            message="reasoning_service.refresh_regime_snapshot is required.",
            context={"regime": regime},
        )
    snapshot = reasoning_service.refresh_regime_snapshot()
    payload = snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)
    if not isinstance(payload, dict) or not payload:
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="REGIME_SNAPSHOT_INVALID",
            message="refresh_regime_snapshot must return a non-empty mapping.",
        )
    return payload
