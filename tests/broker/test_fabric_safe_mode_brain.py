"""T1: Brain-side Fabric SAFE_MODE / disconnect fail-closed (deep-audit residual)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability
from lumina_core.broker.ninjatrader.promotion_gate import NtBridgeAction


@pytest.mark.unit
def test_disconnect_state_safe_blocks_place_not_cancel() -> None:
    """After Brain on_disconnect semantics: connected=False or SAFE → no places."""
    # Simulated post-disconnect connection snapshot (bridge sets SAFE + disconnected)
    conn = NinjaTraderConnectionState(
        state="disconnected",
        account_name="Sim101",
        safe_mode="SAFE",
    )
    assert conn.is_fabric_safe_mode is True
    assert conn.allows_new_orders is False

    ok_p, r_p = assert_nt_bridge_capability(
        action=NtBridgeAction.SUBMIT_ORDER,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
    )
    assert ok_p is False
    assert "disconnected" in r_p or "safe_mode" in r_p


@pytest.mark.unit
def test_connected_full_safe_blocks_place_allows_cancel() -> None:
    conn = NinjaTraderConnectionState(
        state="connected",
        account_name="Sim101",
        safe_mode="FULL_SAFE",
    )
    ok_p, r_p = assert_nt_bridge_capability(
        action=NtBridgeAction.SUBMIT_ORDER,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
    )
    assert ok_p is False
    assert "safe_mode" in r_p

    ok_c, r_c = assert_nt_bridge_capability(
        action=NtBridgeAction.CANCEL,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
    )
    assert ok_c is True
    assert r_c == "ok"


@pytest.mark.unit
def test_place_order_sync_blocks_on_local_safe_mode() -> None:
    from lumina_core.broker.ninjatrader.fabric_client_ops import FabricClientOpsMixin

    class _Fake(FabricClientOpsMixin):
        def __init__(self) -> None:
            self.config = SimpleNamespace(mode_context="sim", trade_mode="sim")
            self.is_connected = True
            self._safe_mode = 2  # SAFE

        @property
        def safe_mode(self) -> int:
            return int(self._safe_mode)

        def _send_and_wait(self, *_a: Any, **_k: Any) -> dict[str, Any]:
            raise AssertionError("must not RPC place while SAFE")

    fake = _Fake()
    order = Order(symbol="MNQ", side="BUY", quantity=1, order_type="MARKET")
    order.metadata = {"decision_context_id": "ctx-safe-1"}
    out = fake.place_order_sync(order, client_order_id="c-safe")
    assert out.get("type") == "error"
    assert out.get("code") == "SAFE_MODE"


@pytest.mark.unit
def test_bridge_on_disconnect_marks_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.broker.ninjatrader.bridge_service import NinjaTraderBridgeService

    bridge = NinjaTraderBridgeService(
        configured_account="Sim101",
        trade_mode="sim",
        ninjatrader_enabled=True,
    )
    # Avoid real fabric
    monkeypatch.setattr(bridge, "get_fabric_client", lambda: None)
    bridge.on_disconnect()
    st = bridge.get_connection_state()
    assert st.state == "disconnected"
    assert st.safe_mode == "SAFE"
    assert st.allows_new_orders is False
