"""Broker bridge facade (re-exports bounded submodules).

CrossTradeBroker is lazy — zero default import (ADR-0040 emergency plugin).
"""

from __future__ import annotations

import random
from typing import Any

from lumina_core.broker.broker_bridge.admission import audit_final_arbitration_reject
from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.factory import broker_factory
from lumina_core.broker.broker_bridge.paper_broker import PaperBroker
from lumina_core.broker.broker_bridge.schemas import (
    AccountInfo,
    Fill,
    Order,
    OrderResult,
    Position,
    paper_position_from_fills,
)
from lumina_core.order_gatekeeper import enforce_pre_trade_gate

__all__ = [
    "AccountInfo",
    "BrokerBridge",
    "CrossTradeBroker",
    "Fill",
    "Order",
    "OrderResult",
    "PaperBroker",
    "Position",
    "audit_final_arbitration_reject",
    "broker_factory",
    "enforce_pre_trade_gate",
    "paper_position_from_fills",
    "random",
]


def __getattr__(name: str) -> Any:
    if name == "CrossTradeBroker":
        from lumina_core.broker.broker_bridge.cross_trade_broker import CrossTradeBroker

        return CrossTradeBroker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
