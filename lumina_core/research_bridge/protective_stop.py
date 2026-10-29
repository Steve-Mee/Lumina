"""Brain-side protective stop. NT native ATM/OCO is not wired (see ADR-0064).

Research team decision (relayed by Steve 2026-10-29): risk-increasing places
require a stop; reduce-only / emergency may flatten without one. Companion STOP
is the enforceable backup while CreateOrder MARKET may ignore StopPrice.
"""

from __future__ import annotations

from lumina_core.broker.broker_bridge.schemas import Order

UNPROTECTED_ENTRY = "unprotected_entry_refused"
PROTECTIVE_STOP_PCT = 0.01
NEEDS_STOP_MODES: frozenset[str] = frozenset({"sim_real_guard", "real"})


def stop_price_of(order: Order) -> float:
    meta = order.metadata if isinstance(order.metadata, dict) else {}
    raw = meta.get("stop_price")
    if raw is None:
        raw = order.stop_loss
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0.0
    value = float(raw)
    if value != value or value <= 0.0:
        return 0.0
    return value


def is_reduce_or_emergency(order: Order) -> bool:
    meta = order.metadata if isinstance(order.metadata, dict) else {}
    if meta.get("reduce_only") is True:
        return True
    if meta.get("emergency") is True:
        return True
    reason = str(meta.get("reason") or "").strip().lower()
    return reason in {"alarm_executor", "flatten", "eod_force_close", "prolonged_disconnect"}


def require_protective_stop(order: Order) -> tuple[bool, str]:
    """Fail-closed for risk-increasing entries without a stop."""
    if is_reduce_or_emergency(order):
        return True, "reduce_only"
    meta = order.metadata if isinstance(order.metadata, dict) else {}
    mode = str(meta.get("mode_context") or "").strip().lower()
    if mode and mode not in NEEDS_STOP_MODES:
        return True, "mode_unprotected_allowed"
    if stop_price_of(order) <= 0.0:
        return False, UNPROTECTED_ENTRY
    return True, "ok"


def default_stop_price(*, side: str, reference: float) -> float:
    price = float(reference)
    if price != price or price <= 0.0:
        raise ValueError(UNPROTECTED_ENTRY)
    token = str(side or "").strip().upper()
    if token == "BUY":
        return price * (1.0 - PROTECTIVE_STOP_PCT)
    if token == "SELL":
        return price * (1.0 + PROTECTIVE_STOP_PCT)
    raise ValueError(UNPROTECTED_ENTRY)


def companion_stop_order(entry: Order, *, client_order_id: str) -> Order:
    """Protected STOP that CancelNonProtected must not cancel."""
    stop = stop_price_of(entry)
    if stop <= 0.0:
        raise ValueError(UNPROTECTED_ENTRY)
    side = "SELL" if str(entry.side).strip().upper() == "BUY" else "BUY"
    meta = dict(entry.metadata) if isinstance(entry.metadata, dict) else {}
    meta = {
        **meta,
        "clientOrderId": client_order_id,
        "reduce_only": True,
        "protected": True,
        "stop_price": stop,
        "reason": "companion_protective_stop",
    }
    return Order(
        symbol=entry.symbol,
        side=side,
        quantity=int(entry.quantity),
        order_type="STOP",
        stop_loss=stop,
        metadata=meta,
    )
