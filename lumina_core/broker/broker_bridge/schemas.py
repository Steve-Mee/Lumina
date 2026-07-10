"""Broker domain dataclasses and paper position helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class Order:
    symbol: str
    side: str
    quantity: int
    order_type: str = "MARKET"
    stop_loss: float = 0.0
    take_profit: float = 0.0
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class OrderResult:
    accepted: bool
    order_id: str
    status: str
    filled_qty: int = 0
    fill_price: float = 0.0
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    # Phase 2 live broker lineage (mirror Fill post-Slice 19; first-class for get_lineage_from_order_result + typed events)
    decision_context_id: str | None = None
    prev_hash: str | None = None
    prev_event_topic: str | None = None


@dataclass(slots=True)
class AccountInfo:
    balance: float
    equity: float
    available_margin: float | None = None
    realized_pnl_today: float = 0.0
    currency: str = "USD"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: int
    avg_price: float
    side: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: str
    commission: float = 0.0

    # Phase 2 Slice 19: First-class lineage fields (promoted from raw)
    decision_context_id: str | None = None
    prev_hash: str | None = None
    prev_event_topic: str | None = None

    raw: dict[str, Any] = field(default_factory=dict)


def paper_position_from_fills(fills: list[Fill], symbol: str) -> Position | None:
    """Net position for ``symbol`` from chronological broker-confirmed fills (paper ledger)."""
    sym = str(symbol).strip()
    rows = [f for f in fills if str(f.symbol).strip() == sym]
    if not rows:
        return None
    rows_sorted = sorted(rows, key=lambda f: f.timestamp)
    net = 0
    avg = 0.0
    for f in rows_sorted:
        q = max(0, int(f.quantity))
        p = float(f.price)
        d = q if str(f.side).upper() == "BUY" else -q
        if net == 0:
            net = d
            avg = p if d != 0 else 0.0
            continue
        new_net = net + d
        if net * d > 0:
            abs_new = abs(new_net)
            avg = (abs(net) * avg + abs(d) * p) / max(abs_new, 1e-9)
            net = new_net
            continue
        if net * new_net > 0:
            net = new_net
            continue
        if new_net == 0:
            net = 0
            avg = 0.0
            continue
        net = new_net
        avg = p
    if net == 0:
        return None
    side = "BUY" if net > 0 else "SELL"
    return Position(symbol=sym, quantity=int(net), avg_price=float(avg), side=side, raw={})
