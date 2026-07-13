"""NT bridge capability matrix by trade_mode."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NtBridgeAction(str, Enum):
    MARKET_DATA = "market_data"
    SUBMIT_ORDER = "submit_order"
    CANCEL = "cancel"


@dataclass(frozen=True, slots=True)
class NtBridgeCapability:
    market_data: bool
    submit_orders: bool
    cancel_orders: bool


_CAPABILITIES: dict[str, NtBridgeCapability] = {
    "paper": NtBridgeCapability(market_data=False, submit_orders=False, cancel_orders=False),
    "sim": NtBridgeCapability(market_data=True, submit_orders=True, cancel_orders=True),
    "sim_real_guard": NtBridgeCapability(market_data=True, submit_orders=True, cancel_orders=True),
    "real": NtBridgeCapability(market_data=True, submit_orders=True, cancel_orders=True),
}


def normalize_trade_mode(mode: str) -> str:
    text = str(mode or "").strip().lower()
    if text in _CAPABILITIES:
        return text
    return "paper"


def resolve_nt_bridge_capability(mode: str) -> NtBridgeCapability:
    return _CAPABILITIES[normalize_trade_mode(mode)]


def action_allowed(mode: str, action: NtBridgeAction) -> bool:
    caps = resolve_nt_bridge_capability(mode)
    if action == NtBridgeAction.MARKET_DATA:
        return caps.market_data
    if action == NtBridgeAction.SUBMIT_ORDER:
        return caps.submit_orders
    if action == NtBridgeAction.CANCEL:
        return caps.cancel_orders
    return False
