"""Mode-aware fail-closed guards for the NinjaTrader bridge."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence

from lumina_core.broker.ninjatrader.account_names import (
    is_broker_demo_name,
    paper_orders_allowed,
)
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction, action_allowed, normalize_trade_mode
from lumina_core.risk.live_release import (
    LIVE_ACCOUNT_PATH_CLOSED_S1,
    LIVE_RELEASE_REQUIRED,
    admit_live_orders,
    live_release_from_engine,
)
from lumina_core.risk.sim_account_guard import admit_sim_account, whitelist_from_engine


def is_broker_demo_account(name: str) -> bool:
    """NinjaTrader brokerage demo, for example DEMO5042070."""
    return is_broker_demo_name(name)


def paper_account_allowed(name: str, mode: str) -> bool:
    """Local Sim is paper. A brokerage DEMO name is paper only outside REAL."""
    return paper_orders_allowed(name, mode)


def s1_guard_kwargs(engine: object | None) -> dict[str, object]:
    """Whitelist + live_release snapshot for NT bridge guards."""
    return {
        "sim_account_whitelist": whitelist_from_engine(engine),
        "live_release": live_release_from_engine(engine),
    }


def _sim_real_guard_enabled() -> bool:
    return str(os.getenv("ENABLE_SIM_REAL_GUARD", "false")).strip().lower() == "true"


def check_account_match(
    *,
    trade_mode: str,
    configured_account: str,
    connected_account: str,
    sim_account_whitelist: Sequence[str] | None = None,
    live_release: Mapping[str, object] | None = None,
    enforce_sim_whitelist: bool = True,
) -> tuple[bool, str]:
    """Verify NT8 connected account matches config for the current mode.

    Whitelist is checked first on new places. Prefix helpers never allow a name.
    Cancel/flatten may skip the whitelist so emergency exits still reach NT.
    """
    mode = normalize_trade_mode(trade_mode)
    configured = str(configured_account or "").strip()
    connected = str(connected_account or "").strip()

    if not connected:
        return False, "ninjatrader_account_unknown"

    if mode == "sim":
        if enforce_sim_whitelist:
            ok, reason = admit_sim_account(connected, sim_account_whitelist, mode=mode)
            if not ok:
                return False, reason
        if configured and connected.lower() != configured.lower():
            return False, f"sim_account_mismatch:expected={configured},actual={connected}"
        return True, "ok"

    if mode == "sim_real_guard":
        if not _sim_real_guard_enabled():
            return False, "sim_real_guard_disabled"
        if enforce_sim_whitelist:
            ok, reason = admit_sim_account(connected, sim_account_whitelist, mode=mode)
            if not ok:
                return False, reason
        if configured and connected.lower() != configured.lower():
            return False, f"sim_real_guard_account_mismatch:expected={configured},actual={connected}"
        return True, "ok"

    if mode == "real":
        if not configured:
            return False, "real_account_not_configured"
        if connected.lower() != configured.lower():
            return False, f"real_account_mismatch:expected={configured},actual={connected}"
        if is_broker_demo_account(configured) or is_broker_demo_account(connected):
            return False, "real_account_blocked_pending_promotion_adr"
        if live_release is None:
            return False, LIVE_RELEASE_REQUIRED
        _ok, reason = admit_live_orders(live_release)
        del _ok
        if reason != LIVE_ACCOUNT_PATH_CLOSED_S1:
            return False, reason
        return False, LIVE_ACCOUNT_PATH_CLOSED_S1

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
    sim_account_whitelist: Sequence[str] | None = None,
    live_release: Mapping[str, object] | None = None,
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
            sim_account_whitelist=sim_account_whitelist,
            live_release=live_release,
            enforce_sim_whitelist=action == NtBridgeAction.SUBMIT_ORDER,
        )
        if not ok:
            return False, reason

    return True, "ok"
