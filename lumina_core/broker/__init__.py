"""Broker package façade.

CrossTradeBroker is lazy (ADR-0040) — zero default import of the emergency plugin.
"""

from __future__ import annotations

from typing import Any

from .broker_bridge import (
    AccountInfo,
    BrokerBridge,
    Fill,
    Order,
    OrderResult,
    PaperBroker,
    Position,
    broker_factory,
    paper_position_from_fills,
)

__all__ = [
    "AccountInfo",
    "BrokerBridge",
    "CrossTradeBroker",
    "Fill",
    "Order",
    "OrderResult",
    "PaperBroker",
    "Position",
    "broker_factory",
    "paper_position_from_fills",
]


def __getattr__(name: str) -> Any:
    if name == "CrossTradeBroker":
        from lumina_core.broker.broker_bridge.cross_trade_broker import CrossTradeBroker

        return CrossTradeBroker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
