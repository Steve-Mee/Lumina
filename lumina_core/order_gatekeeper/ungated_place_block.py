"""S0 D1/D8 tripwire: block risk-increasing places that skip the Validation Gate.

A yaml ``research_execution_mode`` / ``mode`` key is observability only. This
module never reads config or environment to allow a place. The source allow-list
is hardcoded empty. Reopening requires an ADR plus a human-signed release
(not implemented here).

Flatten / cancel / emergency reduce remain allowed only when the order actually
reduces live quantity and cannot flip the sign.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
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


def instrument_root(symbol: object) -> str:
    token = str(symbol or "").strip().upper().split()
    return token[0] if token else ""


def is_risk_reducing_side(
    *,
    order_side: str | None,
    live_position_qty: int,
    order_qty: int | None = None,
) -> bool:
    """True only when side opposes live qty and size cannot flip the sign."""
    side = str(order_side or "").strip().upper()
    if side not in {"BUY", "SELL"}:
        return False
    live = int(live_position_qty)
    if live == 0:
        return False
    if not ((live > 0 and side == "SELL") or (live < 0 and side == "BUY")):
        return False
    if order_qty is None:
        return False
    try:
        qty = int(order_qty)
    except (TypeError, ValueError):
        return False
    return 1 <= qty <= abs(live)


def signed_qty_from_position(pos: object) -> int | None:
    """Signed contracts. Fabric uses abs qty + LONG/SHORT; paper uses a signed net."""
    try:
        raw = int(getattr(pos, "quantity", 0) or 0)
    except (TypeError, ValueError):
        return None
    side = str(getattr(pos, "side", "") or "").strip().upper()
    if side in {"SELL", "SHORT"}:
        return -abs(raw)
    if side in {"BUY", "LONG"}:
        return abs(raw)
    return raw


def flatten_intent_from_position(pos: object) -> tuple[str, int] | None:
    """Close side and signed live qty. ``None`` if flat or the book row is unreadable."""
    signed = signed_qty_from_position(pos)
    if signed is None or signed == 0:
        return None
    return ("SELL" if signed > 0 else "BUY"), signed


def live_qty_from_positions(positions: Iterable[object] | None, symbol: object) -> int | None:
    """Signed book qty for ``symbol`` (root match). ``None`` if the book is unreadable."""
    if positions is None or isinstance(positions, (str, bytes)):
        return None
    want = instrument_root(symbol)
    if not want:
        return None
    total = 0
    matched = False
    try:
        rows = list(positions)
    except (TypeError, ValueError):
        return None
    for pos in rows:
        root = instrument_root(
            getattr(pos, "symbol", None) or getattr(pos, "instrument", None) or ""
        )
        if root != want:
            continue
        signed = signed_qty_from_position(pos)
        if signed is None:
            return None
        total += signed
        matched = True
    return total if matched else 0


def live_qty_from_broker_book(broker: object | None, symbol: object) -> int | None:
    if broker is None:
        return None
    getter = getattr(broker, "get_positions", None)
    if not callable(getter):
        return None
    try:
        return live_qty_from_positions(getter(), symbol)
    except Exception:
        return None


def assert_validation_gate_or_block(
    source: str,
    *,
    reduce_only: bool = False,
    emergency: bool = False,
    order_side: str | None = None,
    live_position_qty: int = 0,
    order_qty: int | None = None,
    source_agent: str = "",
    reason: str = "",
) -> tuple[bool, str]:
    """Return ``(allowed, reason)``. Fail-closed for new risk-increasing orders.

    Does not read yaml, env, ``research_execution_mode``, or ``trade_mode``.
    ``source_agent="research_bridge"`` is not an allow in S0.
    Emergency source/reason spoofing cannot open or flip a position.
    """
    del source_agent  # S0 allow-list is empty; research_bridge cannot place.
    src = str(source or "").strip()
    tagged_exit = bool(emergency) or bool(reduce_only) or src in EMERGENCY_SOURCES or is_emergency_reason(reason)
    reducing = is_risk_reducing_side(
        order_side=order_side,
        live_position_qty=live_position_qty,
        order_qty=order_qty,
    )
    if tagged_exit and reducing:
        emergency_tagged = bool(emergency) or src in EMERGENCY_SOURCES or is_emergency_reason(reason)
        allow_reason = "emergency_flatten_or_cancel_allowed" if emergency_tagged else "reduce_only_allowed"
        logger.info(
            "ungated_place.reduce_allowed",
            extra={"event_data": {"event": "ungated_place.reduce_allowed", "source": src, "reason": allow_reason}},
        )
        return True, allow_reason
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
                "emergency": bool(emergency),
                "order_side": str(order_side or ""),
                "order_qty": order_qty,
                "live_position_qty": int(live_position_qty),
            }
        },
    )
    return False, UNGATED_PLACE_BLOCK_REASON


def inspect_order_flags(order: Order | None) -> tuple[bool, str, str, int | None]:
    """Return ``(reduce_only, reason, order_side, order_qty)``. Fail-closed if missing."""
    if order is None:
        return False, "", "", None
    meta: dict[str, object]
    raw_meta = getattr(order, "metadata", None)
    if isinstance(raw_meta, dict):
        meta = raw_meta
    else:
        meta = {}
    reduce_only = bool(meta.get("reduce_only", False))
    reason = str(meta.get("reason", "") or "")
    order_side = str(getattr(order, "side", "") or "").strip().upper()
    try:
        raw_qty = getattr(order, "quantity", None)
        order_qty = int(raw_qty) if raw_qty is not None else None
    except (TypeError, ValueError):
        order_qty = None
    return reduce_only, reason, order_side, order_qty


def live_qty_from_order_or_engine(order: Order | None, engine: object | None, app: object | None) -> int:
    """Live qty from app/engine only. Order metadata is attacker-controlled and ignored."""
    del order
    if app is not None and hasattr(app, "sim_position_qty"):
        try:
            return int(getattr(app, "sim_position_qty") or 0)
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
    broker: object | None = None,
    live_position_qty: int | None = None,
    source_agent: str = "",
) -> tuple[bool, str]:
    """Convenience wrapper around :func:`assert_validation_gate_or_block` for Order objects."""
    reduce_only, reason, order_side, order_qty = inspect_order_flags(order)
    if live_position_qty is not None:
        qty = int(live_position_qty)
    else:
        symbol = getattr(order, "symbol", None) if order is not None else None
        book = live_qty_from_broker_book(broker, symbol)
        qty = int(book) if book is not None else live_qty_from_order_or_engine(order, engine, app)
    return assert_validation_gate_or_block(
        source,
        reduce_only=reduce_only,
        emergency=emergency,
        order_side=order_side,
        live_position_qty=qty,
        order_qty=order_qty,
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


def blocked_fabric_place_result(reason: str = UNGATED_PLACE_BLOCK_REASON) -> dict[str, object]:
    return {"type": "error", "code": str(reason), "message": str(reason)}
