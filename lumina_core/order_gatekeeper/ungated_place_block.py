"""S0 D1/D8 tripwire: block risk-increasing places that skip the Validation Gate.

A yaml ``research_execution_mode`` / ``mode`` key is observability only. This
module never reads config or environment to allow a place. The source allow-list
is hardcoded empty. Reopening requires an ADR plus a human-signed release
(not implemented here).

Flatten / cancel / emergency reduce remain allowed.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, Final

from lumina_core.broker.broker_bridge.schemas import Order, OrderResult

logger = logging.getLogger("lumina.order_gatekeeper.ungated_place_block")

UNGATED_PLACE_BLOCK_REASON: Final[str] = "UNGATED_PLACE_BLOCKED_S0"

# D8: empty until a later ADR + human-signed release re-arms a named source.
# Yaml, env, and source_agent="research_bridge" cannot populate this set.
S0_PLACE_SOURCE_ALLOWLIST: Final[frozenset[str]] = frozenset()

EMERGENCY_SOURCES: Final[frozenset[str]] = frozenset(
    {
        "emergency_order_endpoints",
        "eod_force_close",
        "heartbeat_watchdog",
        "emergency_flatten_policy",
    }
)

EMERGENCY_REASONS: Final[frozenset[str]] = frozenset(
    {
        "api_emergency_stop",
        "eod_force_close",
        "emergency_flatten",
        "heartbeat_watchdog_flatten",
        "fabric_emergency_flatten",
    }
)

_LEGAL_MODES: Final[frozenset[str]] = frozenset({"off", "shadow", "sim"})


def research_execution_mode_from_mapping(cfg: Mapping[str, Any] | None) -> str:
    """Observability parser. Missing key is ``off``. Never used to allow a place."""
    if cfg is None:
        return "off"
    raw = cfg.get("research_execution_mode")
    if raw is None or str(raw).strip() == "":
        return "off"
    text = str(raw).strip().lower()
    if text not in _LEGAL_MODES:
        return "off"
    return text


def freeze_is_armed() -> bool:
    """S0 freeze is always on. Config cannot disarm it."""
    return True


def is_emergency_reason(reason: object) -> bool:
    return str(reason or "").strip().lower() in EMERGENCY_REASONS


def is_risk_reducing_side(*, order_side: str | None, live_position_qty: int) -> bool:
    side = str(order_side or "").strip().upper()
    if side not in {"BUY", "SELL"}:
        return False
    qty = int(live_position_qty)
    return (qty > 0 and side == "SELL") or (qty < 0 and side == "BUY")


def assert_validation_gate_or_block(
    source: str,
    *,
    reduce_only: bool = False,
    emergency: bool = False,
    order_side: str | None = None,
    live_position_qty: int = 0,
    source_agent: str = "",
    reason: str = "",
) -> tuple[bool, str]:
    """Return ``(allowed, reason)``. Fail-closed for new risk-increasing orders.

    Does not read yaml, env, ``research_execution_mode``, or ``trade_mode``.
    ``source_agent="research_bridge"`` is not an allow in S0.
    """
    del source_agent  # S0 allow-list is empty; research_bridge cannot place.
    src = str(source or "").strip()
    if emergency or src in EMERGENCY_SOURCES or is_emergency_reason(reason):
        logger.info(
            "ungated_place.emergency_allowed",
            extra={"event_data": {"event": "ungated_place.emergency_allowed", "source": src}},
        )
        return True, "emergency_flatten_or_cancel_allowed"
    if reduce_only and is_risk_reducing_side(
        order_side=order_side, live_position_qty=live_position_qty
    ):
        logger.info(
            "ungated_place.reduce_only_allowed",
            extra={"event_data": {"event": "ungated_place.reduce_only_allowed", "source": src}},
        )
        return True, "reduce_only_allowed"
    # D8: the documented source allow-list is never consulted. Yaml, env, and
    # rebinding that set cannot reopen a place. Reopen only via ADR + signed release.
    logger.error(
        "ungated_place.blocked",
        extra={
            "event_data": {
                "event": "ungated_place.blocked",
                "source": src,
                "reason": UNGATED_PLACE_BLOCK_REASON,
                "reduce_only": bool(reduce_only),
                "order_side": str(order_side or ""),
            }
        },
    )
    return False, UNGATED_PLACE_BLOCK_REASON


def inspect_order_flags(order: Order | None) -> tuple[bool, str, str]:
    """Return ``(reduce_only, reason, order_side)`` from an order, fail-closed if missing."""
    if order is None:
        return False, "", ""
    meta: dict[str, object]
    raw_meta = getattr(order, "metadata", None)
    if isinstance(raw_meta, dict):
        meta = raw_meta
    else:
        meta = {}
    reduce_only = bool(meta.get("reduce_only", False))
    reason = str(meta.get("reason", "") or "")
    order_side = str(getattr(order, "side", "") or "").strip().upper()
    return reduce_only, reason, order_side


def live_qty_from_order_or_engine(order: Order | None, engine: object | None, app: object | None) -> int:
    if order is not None:
        meta = getattr(order, "metadata", None)
        if isinstance(meta, dict) and "live_position_qty" in meta:
            try:
                return int(meta["live_position_qty"])
            except (TypeError, ValueError):
                return 0
    if app is not None:
        try:
            return int(getattr(app, "sim_position_qty", 0) or 0)
        except (TypeError, ValueError):
            pass
    if engine is not None:
        try:
            return int(getattr(engine, "live_position_qty", 0) or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def gate_order(
    source: str,
    order: Order | None = None,
    *,
    emergency: bool = False,
    engine: object | None = None,
    app: object | None = None,
    live_position_qty: int | None = None,
    source_agent: str = "",
) -> tuple[bool, str]:
    """Convenience wrapper around :func:`assert_validation_gate_or_block` for Order objects."""
    reduce_only, reason, order_side = inspect_order_flags(order)
    qty = (
        int(live_position_qty)
        if live_position_qty is not None
        else live_qty_from_order_or_engine(order, engine, app)
    )
    return assert_validation_gate_or_block(
        source,
        reduce_only=reduce_only,
        emergency=emergency,
        order_side=order_side,
        live_position_qty=qty,
        source_agent=source_agent,
        reason=reason,
    )


def blocked_order_result(reason: str = UNGATED_PLACE_BLOCK_REASON) -> OrderResult:
    return OrderResult(
        accepted=False,
        order_id="",
        status="rejected",
        message=str(reason),
    )
