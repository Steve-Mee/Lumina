"""NT bridge capability matrix by trade_mode."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class NtBridgeAction(str, Enum):
    MARKET_DATA = "market_data"
    SUBMIT_ORDER = "submit_order"
    CANCEL = "cancel"
    MODIFY_ORDER = "modify_order"


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

_PLACE_FRAMES = frozenset({"submit_order", "place_order"})
_MODIFY_FRAMES = frozenset({"modify_order"})
_CANCEL_FRAMES = frozenset({"cancel", "cancel_order", "cancel_all", "flatten"})
_WHITELIST_ACTIONS = frozenset({NtBridgeAction.SUBMIT_ORDER, NtBridgeAction.MODIFY_ORDER})
_ACCOUNT_ACTIONS = frozenset(
    {NtBridgeAction.SUBMIT_ORDER, NtBridgeAction.MODIFY_ORDER, NtBridgeAction.CANCEL}
)
_SAFE_MODE_BLOCKED_ACTIONS = frozenset({NtBridgeAction.SUBMIT_ORDER, NtBridgeAction.MODIFY_ORDER})
_DISCONNECT_BLOCKED_ACTIONS = frozenset(
    {NtBridgeAction.SUBMIT_ORDER, NtBridgeAction.MODIFY_ORDER, NtBridgeAction.CANCEL}
)


def normalize_trade_mode(mode: str) -> str:
    text = str(mode or "").strip().lower()
    if text in _CAPABILITIES:
        return text
    return "paper"


def resolve_nt_bridge_capability(mode: str) -> NtBridgeCapability:
    return _CAPABILITIES[normalize_trade_mode(mode)]


def action_for_command_frame(frame_type: str) -> NtBridgeAction:
    """Map a Brain command frame to an NT action.

    Unknown types are SUBMIT (whitelist enforced), never CANCEL. CANCEL skip
    is only for explicit flatten/cancel frames so emergency exits still work.
    """
    token = str(frame_type or "").strip().lower()
    if token in _MODIFY_FRAMES:
        return NtBridgeAction.MODIFY_ORDER
    if token in _CANCEL_FRAMES:
        return NtBridgeAction.CANCEL
    if token in _PLACE_FRAMES:
        return NtBridgeAction.SUBMIT_ORDER
    return NtBridgeAction.SUBMIT_ORDER


def action_enforces_sim_whitelist(action: NtBridgeAction) -> bool:
    return action in _WHITELIST_ACTIONS


def action_requires_account_match(action: NtBridgeAction) -> bool:
    return action in _ACCOUNT_ACTIONS


def action_blocked_in_safe_mode(action: NtBridgeAction) -> bool:
    return action in _SAFE_MODE_BLOCKED_ACTIONS


def action_blocked_when_disconnected(action: NtBridgeAction) -> bool:
    return action in _DISCONNECT_BLOCKED_ACTIONS


def action_allowed(mode: str, action: NtBridgeAction) -> bool:
    caps = resolve_nt_bridge_capability(mode)
    if action is NtBridgeAction.MARKET_DATA:
        return caps.market_data
    if action is NtBridgeAction.SUBMIT_ORDER:
        return caps.submit_orders
    if action is NtBridgeAction.MODIFY_ORDER:
        return caps.submit_orders
    if action is NtBridgeAction.CANCEL:
        return caps.cancel_orders
    return False
