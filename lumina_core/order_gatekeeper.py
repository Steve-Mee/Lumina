from __future__ import annotations

from typing import Any


def resolve_regime_snapshot(engine: Any, regime: str | None = None) -> dict[str, Any]:
    """Resolve and refresh the active regime snapshot used by risk/session gates."""
    reasoning_service = getattr(engine, "reasoning_service", None)
    if reasoning_service is not None and hasattr(reasoning_service, "refresh_regime_snapshot"):
        snapshot = reasoning_service.refresh_regime_snapshot()
        return snapshot.to_dict() if hasattr(snapshot, "to_dict") else dict(snapshot)

    existing = getattr(engine, "current_regime_snapshot", {})
    if isinstance(existing, dict) and existing:
        return existing

    label = str(regime or getattr(engine, "market_regime", "NEUTRAL") or "NEUTRAL")
    fallback = {
        "label": label,
        "risk_state": "NORMAL",
        "adaptive_policy": {
            "risk_multiplier": 1.0,
            "cooldown_minutes": 30,
            "high_risk": False,
        },
    }
    engine.current_regime_snapshot = fallback
    return fallback


def enforce_pre_trade_gate(
    engine: Any,
    *,
    symbol: str,
    regime: str,
    proposed_risk: float,
) -> tuple[bool, str]:
    """Single pre-trade gatekeeper for SessionGuard + HardRiskController."""
    risk_controller = getattr(engine, "risk_controller", None)
    if not risk_controller:
        return False, "Risk controller not available"

    limits = getattr(risk_controller, "_active_limits", None)
    enforce_session_guard = bool(getattr(limits, "enforce_session_guard", True))
    session_guard = getattr(engine, "session_guard", None)
    if enforce_session_guard:
        if session_guard is None:
            return False, "Session guard unavailable (fail-closed)"
        if session_guard.is_rollover_window():
            return False, "Session guard blocked order: rollover window active"
        if not session_guard.is_trading_session():
            next_open = session_guard.next_open() if hasattr(session_guard, "next_open") else None
            suffix = f" | next_open={next_open.isoformat()}" if next_open is not None else ""
            return False, f"Session guard blocked order: outside trading session{suffix}"

    snapshot = resolve_regime_snapshot(engine, regime)
    adaptive = snapshot.get("adaptive_policy", {}) if isinstance(snapshot, dict) else {}
    risk_controller.apply_regime_override(
        regime=str(snapshot.get("label", regime or "NEUTRAL")),
        risk_state=str(snapshot.get("risk_state", "NORMAL")),
        risk_multiplier=float(adaptive.get("risk_multiplier", 1.0) or 1.0),
        cooldown_after_streak=int(adaptive.get("cooldown_minutes", 30) or 30),
    )
    return risk_controller.check_can_trade(symbol, str(snapshot.get("label", regime)), proposed_risk)
