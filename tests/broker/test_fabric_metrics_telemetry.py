"""PR-E: Fabric client metrics and telemetry block shape."""

from __future__ import annotations

from lumina_core.broker.ninjatrader.bridge_service import NinjaTraderBridgeService
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.fabric_metrics import FabricClientMetrics


def test_fabric_client_metrics_rtt_percentiles() -> None:
    m = FabricClientMetrics()
    m.record_place(ok=True, rtt_ms=1.0)
    m.record_place(ok=True, rtt_ms=2.0)
    m.record_place(ok=False, rtt_ms=10.0)
    m.record_connect(ok=True)
    m.record_safety_alert()
    snap = m.snapshot()
    assert snap["fabric_client_place_total"] == 3
    assert snap["fabric_client_place_ok"] == 2
    assert snap["fabric_client_place_error"] == 1
    assert snap["fabric_client_rtt_samples"] == 3
    assert snap["fabric_client_rtt_ms_p50"] >= 1.0
    assert snap["fabric_client_connect_ok"] == 1
    assert snap["fabric_client_safety_alerts"] == 1


def test_connection_state_telemetry_includes_fabric_fields() -> None:
    state = NinjaTraderConnectionState(
        state="connected",
        account_name="Sim101",
        safe_mode="NORMAL",
        fabric_target="127.0.0.1:50051",
        gateway="fabric",
        last_state_hash="abc",
        recent_alerts=2,
        metrics={"fabric_client_place_total": 5},
    )
    d = state.to_telemetry_dict()
    assert d["connected"] is True
    assert d["safe_mode"] == "NORMAL"
    assert d["fabric_target"] == "127.0.0.1:50051"
    assert d["gateway"] == "fabric"
    assert d["recent_alerts"] == 2
    assert d["metrics"]["fabric_client_place_total"] == 5


def test_bridge_get_connection_state_exposes_metrics() -> None:
    bridge = NinjaTraderBridgeService(
        configured_account="Sim101",
        trade_mode="sim",
        ninjatrader_enabled=True,
    )
    bridge.metrics.record_place(ok=True, rtt_ms=3.5)
    bridge.authenticate_session(session_id="s1", account_name="Sim101")
    st = bridge.get_connection_state()
    assert st.account_name == "Sim101"
    assert st.is_connected
    tel = st.to_telemetry_dict()
    assert "metrics" in tel
    assert tel["metrics"]["fabric_client_place_ok"] == 1
