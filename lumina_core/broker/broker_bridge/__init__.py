"""Broker bridge facade (re-exports bounded submodules)."""

from __future__ import annotations

import random

from lumina_core.broker.broker_bridge.admission import audit_final_arbitration_reject
from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.cross_trade_broker import CrossTradeBroker
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
