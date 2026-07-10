"""Shared engine accessors for the pre-trade gate."""

from __future__ import annotations

from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.logging_utils import get_logger

_LOG = get_logger("lumina.trading.gate")
MODES_REQUIRING_EQUITY_SNAPSHOT = frozenset({"real", "paper", "sim_real_guard"})


def logger_for_engine(engine: Any):
    app = getattr(engine, "app", None)
    logger = getattr(app, "logger", None)
    return logger if logger is not None else _LOG


def safe_log_warning(engine: Any, message: str) -> None:
    logger_for_engine(engine).warning(message)


def record_mode_guard_block(engine: Any, *, mode: str, reason: str) -> None:
    obs = getattr(engine, "observability_service", None)
    if obs is not None and hasattr(obs, "record_mode_guard_block"):
        obs.record_mode_guard_block(mode=str(mode), reason=str(reason))


def audit_trade_decision(engine: Any, payload: dict[str, Any], *, mode: str) -> bool:
    service = getattr(engine, "audit_log_service", None)
    if service is None or not hasattr(service, "log_decision"):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="AUDIT_LOG_SERVICE_MISSING",
            message="audit_log_service.log_decision is required for pre-trade enforcement.",
        )
    return bool(service.log_decision(payload, is_real_mode=str(mode).lower() == "real"))


def resolve_blackboard(engine: Any) -> Any | None:
    board = getattr(engine, "blackboard", None)
    if board is not None:
        return board
    app = getattr(engine, "app", None)
    return getattr(app, "blackboard", None)


def resolve_event_bus(engine: Any) -> Any | None:
    return getattr(engine, "event_bus", None)


def is_risk_reducing_side(*, engine: Any, order_side: str | None) -> bool:
    side = str(order_side or "").strip().upper()
    if side not in {"BUY", "SELL"}:
        return False
    live_qty = int(getattr(engine, "live_position_qty", 0) or 0)
    return (live_qty > 0 and side == "SELL") or (live_qty < 0 and side == "BUY")
