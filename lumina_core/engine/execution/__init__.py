"""Bounded context: Execution — order routing, trade reconciliation, engine core.

This package re-exports from the canonical engine-level modules.
Modules will be physically moved here in a future migration sprint (ADR-002).

Current members:
    LuminaEngine    — main trading loop and signal aggregation
    OrderGatekeeper — pre-order safety validation
    TradeReconciler — fill reconciliation and audit
"""

from __future__ import annotations

from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.order_gatekeeper import OrderGatekeeper
from lumina_core.engine.trade_reconciler import TradeReconciler

__all__ = [
    "LuminaEngine",
    "OrderGatekeeper",
    "TradeReconciler",
]
