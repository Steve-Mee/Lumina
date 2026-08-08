"""Mode-aware fail-closed guards for the NinjaTrader bridge."""

from __future__ import annotations

import os
import re

from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction, action_allowed, normalize_trade_mode

_SIM_ACCOUNT_RE = re.compile(r"^sim", re.IGNORECASE)


def _sim_real_guard_enabled() -> bool:
    return str(os.getenv("ENABLE_SIM_REAL_GUARD", "false")).strip().lower() == "true"


def check_account_match(
    *,
    trade_mode: str,
    configured_account: str,
    connected_account: str,
) -> tuple[bool, str]:
    """Verify NT8 connected account matches config for the current mode."""
    mode = normalize_trade_mode(trade_mode)
    configured = str(configured_account or "").strip()
    connected = str(connected_account or "").strip()

    if not connected:
        return False, "ninjatrader_account_unknown"

    if mode == "sim":
        if configured and connected.lower() != configured.lower():
            return False, f"sim_account_mismatch:expected={configured},actual={connected}"
        if configured and not _SIM_ACCOUNT_RE.match(configured):
            return False, f"sim_account_not_sim_named:{configured}"
        return True, "ok"

    if mode == "sim_real_guard":
        if not _sim_real_guard_enabled():
            return False, "sim_real_guard_disabled"
        if configured and connected.lower() != configured.lower():
            return False, f"sim_real_guard_account_mismatch:expected={configured},actual={connected}"
        return True, "ok"

    if mode == "real":
        if not configured:
            return False, "real_account_not_configured"
        if connected.lower() != configured.lower():
            return False, f"real_account_mismatch:expected={configured},actual={connected}"
        return True, "ok"

    return False, f"nt_bridge_not_allowed_in_mode:{mode}"


def check_disconnect_policy(
    *,
    trade_mode: str,
    connection: NinjaTraderConnectionState,
    action: NtBridgeAction,
) -> tuple[bool, str]:
    """Fail-closed when disconnected for order actions in live-ish modes."""
    mode = normalize_trade_mode(trade_mode)
    if action in {NtBridgeAction.SUBMIT_ORDER, NtBridgeAction.CANCEL}:
        if not connection.is_connected:
            if mode in {"sim", "sim_real_guard", "real"}:
                return False, f"ninjatrader_disconnected:{connection.state}"
            return False, "ninjatrader_disconnected"
    return True, "ok"


def check_safe_mode_policy(
    *,
    connection: NinjaTraderConnectionState,
    action: NtBridgeAction,
) -> tuple[bool, str]:
    """Fabric SAFE_MODE: reject new place/modify; allow cancel/flatten (runbook).

    Host cancels non-protected on disconnect/timeout; Brain must not place while SAFE.
    """
    if action == NtBridgeAction.SUBMIT_ORDER and connection.is_fabric_safe_mode:
        return False, f"fabric_safe_mode_blocks_place:{connection.safe_mode}"
    return True, "ok"


def assert_nt_bridge_capability(
    *,
    action: NtBridgeAction,
    trade_mode: str,
    connection: NinjaTraderConnectionState,
    configured_account: str = "",
    ninjatrader_enabled: bool = True,
) -> tuple[bool, str]:
    """Combined promotion + connection + account guard for NT bridge actions."""
    mode = normalize_trade_mode(trade_mode)

    if not ninjatrader_enabled:
        return False, "ninjatrader_bridge_disabled"

    if not action_allowed(mode, action):
        return False, f"nt_bridge_action_blocked:{action.value}:mode={mode}"

    ok, reason = check_disconnect_policy(trade_mode=mode, connection=connection, action=action)
    if not ok:
        return False, reason

    ok, reason = check_safe_mode_policy(connection=connection, action=action)
    if not ok:
        return False, reason

    if action in {NtBridgeAction.SUBMIT_ORDER, NtBridgeAction.CANCEL}:
        ok, reason = check_account_match(
            trade_mode=mode,
            configured_account=configured_account,
            connected_account=connection.account_name,
        )
        if not ok:
            return False, reason

    return True, "ok"
