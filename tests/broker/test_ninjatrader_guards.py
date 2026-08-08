from __future__ import annotations


import pytest

from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability, check_account_match
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction


def _connected(account: str = "Sim101") -> NinjaTraderConnectionState:
    return NinjaTraderConnectionState(state="connected", account_name=account)


def test_paper_mode_blocks_all_actions() -> None:
    conn = _connected()
    for action in NtBridgeAction:
        ok, reason = assert_nt_bridge_capability(
            action=action,
            trade_mode="paper",
            connection=conn,
            configured_account="Sim101",
            ninjatrader_enabled=True,
        )
        assert ok is False
        assert "blocked" in reason or "disabled" in reason or "not_allowed" in reason


def test_sim_allows_submit_when_connected_and_account_matches() -> None:
    ok, reason = assert_nt_bridge_capability(
        action=NtBridgeAction.SUBMIT_ORDER,
        trade_mode="sim",
        connection=_connected("Sim101"),
        configured_account="Sim101",
        ninjatrader_enabled=True,
    )
    assert ok is True
    assert reason == "ok"


def test_sim_rejects_account_mismatch() -> None:
    ok, reason = check_account_match(
        trade_mode="sim",
        configured_account="Sim101",
        connected_account="Sim202",
    )
    assert ok is False
    assert "mismatch" in reason


def test_real_requires_exact_account_match() -> None:
    ok, reason = check_account_match(
        trade_mode="real",
        configured_account="LiveAcct",
        connected_account="LiveAcct",
    )
    assert ok is True

    ok, reason = check_account_match(
        trade_mode="real",
        configured_account="LiveAcct",
        connected_account="OtherAcct",
    )
    assert ok is False
    assert "mismatch" in reason


def test_disconnect_blocks_orders_in_sim() -> None:
    conn = NinjaTraderConnectionState(state="disconnected", account_name="Sim101")
    ok, reason = assert_nt_bridge_capability(
        action=NtBridgeAction.SUBMIT_ORDER,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
    )
    assert ok is False
    assert "disconnected" in reason


def test_fabric_safe_mode_blocks_place_allows_cancel() -> None:
    """Track E residual: SAFE_MODE rejects place; cancel remains allowed when connected."""
    conn = NinjaTraderConnectionState(
        state="connected",
        account_name="Sim101",
        safe_mode="SAFE",
    )
    assert conn.is_fabric_safe_mode is True
    assert conn.allows_new_orders is False

    ok_place, reason_place = assert_nt_bridge_capability(
        action=NtBridgeAction.SUBMIT_ORDER,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
    )
    assert ok_place is False
    assert "safe_mode" in reason_place

    ok_cancel, reason_cancel = assert_nt_bridge_capability(
        action=NtBridgeAction.CANCEL,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
    )
    assert ok_cancel is True
    assert reason_cancel == "ok"


def test_sim_real_guard_requires_feature_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_SIM_REAL_GUARD", "false")
    ok, reason = check_account_match(
        trade_mode="sim_real_guard",
        configured_account="Sim101",
        connected_account="Sim101",
    )
    assert ok is False
    assert "disabled" in reason


def test_ninjatrader_disabled_blocks_actions() -> None:
    ok, reason = assert_nt_bridge_capability(
        action=NtBridgeAction.SUBMIT_ORDER,
        trade_mode="sim",
        connection=_connected(),
        configured_account="Sim101",
        ninjatrader_enabled=False,
    )
    assert ok is False
    assert reason == "ninjatrader_bridge_disabled"
