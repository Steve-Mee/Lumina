"""NinjaTrader 8 native broker bridge — bounded context (Execution Fabric).

Exports are lazy so Risk Core can import ``account_names`` without loading the
bridge (ADR-0061). Eager imports here closed a cycle:
``sim_account_guard`` → this package → ``guards`` → ``sim_account_guard``.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "FabricConfig",
    "FabricGrpcClient",
    "NinjaTraderBridgeService",
    "NinjaTraderBroker",
    "NinjaTraderConnectionState",
    "NtBridgeAction",
    "assert_nt_bridge_capability",
    "get_ninjatrader_bridge_service",
    "reset_ninjatrader_bridge_service",
]


def __getattr__(name: str) -> Any:
    if name in {"FabricConfig", "FabricGrpcClient"}:
        from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient

        return {"FabricConfig": FabricConfig, "FabricGrpcClient": FabricGrpcClient}[name]
    if name in {"NinjaTraderBridgeService", "get_ninjatrader_bridge_service", "reset_ninjatrader_bridge_service"}:
        from lumina_core.broker.ninjatrader.bridge_service import (
            NinjaTraderBridgeService,
            get_ninjatrader_bridge_service,
            reset_ninjatrader_bridge_service,
        )

        return {
            "NinjaTraderBridgeService": NinjaTraderBridgeService,
            "get_ninjatrader_bridge_service": get_ninjatrader_bridge_service,
            "reset_ninjatrader_bridge_service": reset_ninjatrader_bridge_service,
        }[name]
    if name == "NinjaTraderBroker":
        from lumina_core.broker.ninjatrader.broker import NinjaTraderBroker

        return NinjaTraderBroker
    if name == "NinjaTraderConnectionState":
        from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState

        return NinjaTraderConnectionState
    if name == "NtBridgeAction":
        from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction

        return NtBridgeAction
    if name == "assert_nt_bridge_capability":
        from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability

        return assert_nt_bridge_capability
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
