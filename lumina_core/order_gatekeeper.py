from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any


_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


_LOG = logging.getLogger(__name__)


def _logger_for_engine(engine: Any):
    app = getattr(engine, "app", None)
    logger = getattr(app, "logger", None)
    return logger if logger is not None else _LOG


def _safe_log_warning(engine: Any, message: str) -> None:
    logger = _logger_for_engine(engine)
    try:
        logger.warning(message)
    except Exception:
        _LOG.warning(message)


def _parse_contract_symbol(symbol: str) -> tuple[str | None, int | None, int | None]:
    text = str(symbol or "").strip().upper()
    parts = text.split()
    if len(parts) < 2:
        return None, None, None

    code = parts[1]
    if len(code) != 5:
        return None, None, None

    month = _MONTHS.get(code[:3])
    if month is None:
        return None, None, None

    try:
        year = 2000 + int(code[3:5])
    except ValueError:
        return None, None, None

    root = parts[0] if parts else None
    return root, month, year


def _third_friday(year: int, month: int) -> datetime:
    first = datetime(year, month, 1, tzinfo=timezone.utc)
    weekday = first.weekday()  # Monday=0
    days_to_friday = (4 - weekday) % 7
    first_friday_day = 1 + days_to_friday
    third_friday_day = first_friday_day + 14
    return datetime(year, month, third_friday_day, 23, 59, 59, tzinfo=timezone.utc)


def is_stale_contract_symbol(symbol: str, *, now_utc: datetime | None = None) -> bool:
    """Return True when a futures contract symbol is clearly past expiry month.

    Expected format example: "MES JUN26".
    If parsing fails, return False to avoid false blocking.
    """
    _root, month, year = _parse_contract_symbol(symbol)
    if month is None or year is None:
        return False

    now = now_utc or datetime.now(timezone.utc)
    # Calendar-aware expiry approximation (3rd Friday of contract month, CME style futures).
    expiry_utc = _third_friday(int(year), int(month))
    return now > expiry_utc


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

    try:
        if session_guard.is_rollover_window():
            return False, "rollover_window"
        if not session_guard.is_trading_session():
            return False, "outside_trading_session"
    except Exception:
        return False, "session_guard_check_failed"

    return True, "ok"


def _broker_metadata_contract_allowed(engine: Any, symbol: str) -> tuple[bool, str]:
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
        try:
            ok, reason = broker.is_contract_tradeable(str(symbol))
            return bool(ok), str(reason or "broker_metadata_gate")
        except Exception:
            return False, "broker_metadata_check_failed"

    # Optional metadata dictionary capability.
    if hasattr(broker, "get_contract_metadata"):
        try:
            meta = broker.get_contract_metadata(str(symbol))
            if isinstance(meta, dict):
                if bool(meta.get("expired", False)):
                    return False, "broker_metadata_expired"
                if meta.get("tradeable") is False:
                    return False, "broker_metadata_not_tradeable"
        except Exception:
            return False, "broker_metadata_check_failed"

    return True, "ok"


def _audit_stale_override(engine: Any, symbol: str, mode: str) -> None:
    _safe_log_warning(
        engine,
        (
            "OVERRIDE_AUDIT,gate=stale_contract,"
            f"mode={mode},symbol={symbol},source=LUMINA_ALLOW_STALE_CONTRACTS"
        ),
    )


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
    mode = str(getattr(getattr(engine, "config", None), "trade_mode", "paper") or "paper").strip().lower()
    allow_stale = os.getenv("LUMINA_ALLOW_STALE_CONTRACTS", "false").strip().lower() == "true"
    if mode in {"sim", "real"}:
        stale_contract = is_stale_contract_symbol(symbol)
        if stale_contract and not allow_stale:
            return False, f"Contract symbol stale/expired by calendar check: {symbol}"
        if stale_contract and allow_stale:
            _audit_stale_override(engine, symbol, mode)

        broker_ok, broker_reason = _broker_metadata_contract_allowed(engine, symbol)
        if not broker_ok:
            return False, f"Contract blocked by broker metadata: {symbol} ({broker_reason})"

    risk_controller = getattr(engine, "risk_controller", None)
    if not risk_controller:
        return False, "Risk controller not available"

    session_ok, session_reason = session_guard_allows_trading(engine)
    if not session_ok:
        session_guard = getattr(engine, "session_guard", None)
        next_open = session_guard.next_open() if (session_guard is not None and hasattr(session_guard, "next_open")) else None
        suffix = f" | next_open={next_open.isoformat()}" if next_open is not None else ""
        return False, f"Session guard blocked order: {session_reason}{suffix}"

    snapshot = resolve_regime_snapshot(engine, regime)
    adaptive = snapshot.get("adaptive_policy", {}) if isinstance(snapshot, dict) else {}
    risk_controller.apply_regime_override(
        regime=str(snapshot.get("label", regime or "NEUTRAL")),
        risk_state=str(snapshot.get("risk_state", "NORMAL")),
        risk_multiplier=float(adaptive.get("risk_multiplier", 1.0) or 1.0),
        cooldown_after_streak=int(adaptive.get("cooldown_minutes", 30) or 30),
    )
    return risk_controller.check_can_trade(symbol, str(snapshot.get("label", regime)), proposed_risk)
