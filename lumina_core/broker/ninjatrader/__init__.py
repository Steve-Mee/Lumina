"""NinjaTrader 8 native broker bridge — bounded context."""

from lumina_core.broker.ninjatrader.bridge_service import (
    NinjaTraderBridgeService,
    get_ninjatrader_bridge_service,
    reset_ninjatrader_bridge_service,
)
from lumina_core.broker.ninjatrader.broker import NinjaTraderBroker
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction

__all__ = [
    "NinjaTraderBridgeService",
    "NinjaTraderBroker",
    "NinjaTraderConnectionState",
    "NtBridgeAction",
    "assert_nt_bridge_capability",
    "get_ninjatrader_bridge_service",
    "reset_ninjatrader_bridge_service",
]
