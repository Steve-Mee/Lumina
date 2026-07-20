"""Contract tests for Execution Fabric proto (lumina.execution.v1)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROTO_FILE = REPO_ROOT / "protos" / "lumina" / "execution" / "v1" / "fabric.proto"


def test_fabric_proto_file_exists() -> None:
    assert PROTO_FILE.is_file(), f"missing SSOT proto: {PROTO_FILE}"


def test_fabric_proto_declares_package_and_service() -> None:
    text = PROTO_FILE.read_text(encoding="utf-8")
    assert "package lumina.execution.v1;" in text
    assert "service ExecutionFabric" in text
    assert "rpc TradingStream" in text
    assert "rpc GetAccountState" in text
    assert "client_order_id" in text
    assert "SAFE_MODE_STATE_SAFE" in text


def test_generated_stubs_importable() -> None:
    pytest.importorskip("grpc")
    from lumina_core.broker.ninjatrader.generated import fabric_pb2, fabric_pb2_grpc

    assert fabric_pb2.DESCRIPTOR.package == "lumina.execution.v1"
    assert hasattr(fabric_pb2_grpc, "ExecutionFabricStub")
    assert hasattr(fabric_pb2_grpc, "ExecutionFabricServicer")


def test_place_order_command_roundtrip() -> None:
    pytest.importorskip("grpc")
    from lumina_core.broker.ninjatrader.generated import fabric_pb2

    cmd = fabric_pb2.PlaceOrderCommand(
        client_order_id="11111111-1111-4111-8111-111111111111",
        instrument="MNQ",
        action=fabric_pb2.ORDER_ACTION_BUY,
        quantity=1,
        order_type=fabric_pb2.ORDER_TYPE_MARKET,
        time_in_force=fabric_pb2.TIME_IN_FORCE_DAY,
        reduce_only=False,
        protected=False,
        correlation_id="corr-1",
        mode_context="sim",
    )
    raw = cmd.SerializeToString()
    restored = fabric_pb2.PlaceOrderCommand()
    restored.ParseFromString(raw)
    assert restored.client_order_id == cmd.client_order_id
    assert restored.instrument == "MNQ"
    assert restored.action == fabric_pb2.ORDER_ACTION_BUY
    assert restored.quantity == 1


def test_brain_and_fabric_envelopes_support_heartbeat() -> None:
    pytest.importorskip("grpc")
    from lumina_core.broker.ninjatrader.generated import fabric_pb2

    brain = fabric_pb2.BrainMessage(
        heartbeat=fabric_pb2.Heartbeat(
            sequence_number=1,
            timestamp_unix_ms=1_700_000_000_000,
            brain_status="ok",
        )
    )
    assert brain.WhichOneof("payload") == "heartbeat"

    fabric = fabric_pb2.FabricMessage(
        safety_alert=fabric_pb2.SafetyAlert(
            alert_type=fabric_pb2.SAFETY_ALERT_TYPE_HEARTBEAT_TIMEOUT,
            severity=fabric_pb2.SAFETY_SEVERITY_CRITICAL,
            message="heartbeat timeout",
            recommended_action="cancel_and_safe_mode",
            timestamp_unix_ms=1_700_000_000_500,
        )
    )
    assert fabric.WhichOneof("payload") == "safety_alert"
    assert fabric.safety_alert.alert_type == fabric_pb2.SAFETY_ALERT_TYPE_HEARTBEAT_TIMEOUT


def test_state_sync_contains_orders_and_positions() -> None:
    pytest.importorskip("grpc")
    from lumina_core.broker.ninjatrader.generated import fabric_pb2

    sync = fabric_pb2.StateSyncResponse(
        open_orders=[
            fabric_pb2.WorkingOrder(
                client_order_id="c1",
                nt_order_id="nt1",
                instrument="MNQ",
                action=fabric_pb2.ORDER_ACTION_BUY,
                quantity=1,
                state=fabric_pb2.ORDER_STATE_WORKING,
            )
        ],
        positions=[
            fabric_pb2.PositionUpdate(
                instrument="MNQ",
                quantity=1,
                avg_price=21000.25,
                side="LONG",
            )
        ],
        account=fabric_pb2.AccountMetrics(
            balance=100_000.0,
            equity=100_050.0,
            account_name="Sim101",
            currency="USD",
        ),
        safe_mode=fabric_pb2.SAFE_MODE_STATE_NORMAL,
        state_hash="abc",
    )
    assert len(sync.open_orders) == 1
    assert sync.account.account_name == "Sim101"
    assert sync.safe_mode == fabric_pb2.SAFE_MODE_STATE_NORMAL
