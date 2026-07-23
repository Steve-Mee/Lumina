"""Chaos / safety-matrix tests for Execution Fabric client + bridge (PR-D)."""

from __future__ import annotations

import time
import uuid
from concurrent import futures
from typing import Iterator

import pytest

pytest.importorskip("grpc")

import grpc

from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.broker.ninjatrader.bridge_service import NinjaTraderBridgeService
from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient
from lumina_core.broker.ninjatrader.generated import fabric_pb2, fabric_pb2_grpc


class _ChaosFabricServicer(fabric_pb2_grpc.ExecutionFabricServicer):
    """Mock Fabric with SAFE_MODE, idempotency, working limit orders, disconnect simulation."""

    def __init__(self, *, expected_token: str = "chaos-token") -> None:
        self.expected_token = expected_token
        self.account = "Sim101"
        self.safe_mode = False
        self.place_by_id: dict[str, fabric_pb2.OrderEvent] = {}
        self.working: dict[str, fabric_pb2.WorkingOrder] = {}
        self.place_count = 0
        self.drop_heartbeats = False
        self._seq = 0

    def TradingStream(self, request_iterator, context):  # noqa: N802, ANN001
        authed = False
        for msg in request_iterator:
            which = msg.WhichOneof("payload")
            if which == "auth_hello":
                ok = msg.auth_hello.token == self.expected_token
                authed = ok
                yield fabric_pb2.FabricMessage(
                    auth_result=fabric_pb2.AuthResult(
                        ok=ok,
                        session_id="chaos-sess" if ok else "",
                        account_name=self.account if ok else "",
                        code="OK" if ok else "AUTH_FAILED",
                        message="ok" if ok else "bad token",
                    )
                )
                if ok:
                    yield fabric_pb2.FabricMessage(
                        state_sync=fabric_pb2.StateSyncResponse(
                            account=fabric_pb2.AccountMetrics(
                                balance=100_000.0,
                                equity=100_000.0,
                                account_name=self.account,
                                currency="USD",
                            ),
                            safe_mode=fabric_pb2.SAFE_MODE_STATE_NORMAL,
                            state_hash="deadbeefcafebabe",
                            timestamp_unix_ms=int(time.time() * 1000),
                        )
                    )
                continue

            if not authed:
                yield fabric_pb2.FabricMessage(
                    command_reject=fabric_pb2.CommandReject(
                        code="UNAUTHENTICATED",
                        message="auth required",
                    )
                )
                continue

            if which == "heartbeat":
                if self.drop_heartbeats:
                    continue
                mode = (
                    fabric_pb2.SAFE_MODE_STATE_SAFE
                    if self.safe_mode
                    else fabric_pb2.SAFE_MODE_STATE_NORMAL
                )
                yield fabric_pb2.FabricMessage(
                    heartbeat=fabric_pb2.Heartbeat(
                        sequence_number=msg.heartbeat.sequence_number,
                        timestamp_unix_ms=int(time.time() * 1000),
                        fabric_safe_mode=mode,
                    )
                )
                continue

            if which == "place_order":
                po = msg.place_order
                self.place_count += 1
                if po.client_order_id in self.place_by_id:
                    # Idempotent replay of last event
                    yield fabric_pb2.FabricMessage(order_event=self.place_by_id[po.client_order_id])
                    continue
                if self.safe_mode:
                    yield fabric_pb2.FabricMessage(
                        command_reject=fabric_pb2.CommandReject(
                            correlation_id=po.correlation_id,
                            client_order_id=po.client_order_id,
                            code="SAFE_MODE",
                            message="safe mode blocks place",
                            safe_mode=fabric_pb2.SAFE_MODE_STATE_SAFE,
                        )
                    )
                    continue
                self._seq += 1
                nt_id = f"nt-chaos-{self._seq}"
                if po.order_type in (fabric_pb2.ORDER_TYPE_LIMIT, fabric_pb2.ORDER_TYPE_STOP):
                    wo = fabric_pb2.WorkingOrder(
                        client_order_id=po.client_order_id,
                        nt_order_id=nt_id,
                        instrument=po.instrument,
                        action=po.action,
                        quantity=po.quantity,
                        order_type=po.order_type,
                        price=po.price,
                        state=fabric_pb2.ORDER_STATE_WORKING,
                        protected=po.protected,
                        reduce_only=po.reduce_only,
                    )
                    self.working[po.client_order_id] = wo
                    evt = fabric_pb2.OrderEvent(
                        client_order_id=po.client_order_id,
                        nt_order_id=nt_id,
                        state=fabric_pb2.ORDER_STATE_WORKING,
                        instrument=po.instrument,
                        action=po.action,
                        correlation_id=po.correlation_id,
                        timestamp_unix_ms=int(time.time() * 1000),
                    )
                    self.place_by_id[po.client_order_id] = evt
                    yield fabric_pb2.FabricMessage(order_event=evt)
                    continue

                evt = fabric_pb2.OrderEvent(
                    client_order_id=po.client_order_id,
                    nt_order_id=nt_id,
                    state=fabric_pb2.ORDER_STATE_FILLED,
                    filled_qty=po.quantity,
                    avg_fill_price=21000.0,
                    instrument=po.instrument,
                    action=po.action,
                    correlation_id=po.correlation_id,
                    timestamp_unix_ms=int(time.time() * 1000),
                )
                self.place_by_id[po.client_order_id] = evt
                yield fabric_pb2.FabricMessage(order_event=evt)
                continue

            if which == "cancel_order":
                co = msg.cancel_order
                self.working.pop(co.client_order_id, None)
                yield fabric_pb2.FabricMessage(
                    order_event=fabric_pb2.OrderEvent(
                        client_order_id=co.client_order_id,
                        nt_order_id=co.nt_order_id or "nt-x",
                        state=fabric_pb2.ORDER_STATE_CANCELLED,
                        correlation_id=co.correlation_id,
                        timestamp_unix_ms=int(time.time() * 1000),
                    )
                )
                continue

            if which == "modify_order":
                mo = msg.modify_order
                wo = self.working.get(mo.client_order_id)
                if wo is None:
                    yield fabric_pb2.FabricMessage(
                        order_event=fabric_pb2.OrderEvent(
                            client_order_id=mo.client_order_id,
                            state=fabric_pb2.ORDER_STATE_REJECTED,
                            rejection_reason="order_not_found",
                            correlation_id=mo.correlation_id,
                            timestamp_unix_ms=int(time.time() * 1000),
                        )
                    )
                    continue
                if mo.quantity > 0:
                    wo.quantity = mo.quantity
                if mo.price > 0:
                    wo.price = mo.price
                yield fabric_pb2.FabricMessage(
                    order_event=fabric_pb2.OrderEvent(
                        client_order_id=wo.client_order_id,
                        nt_order_id=wo.nt_order_id,
                        state=fabric_pb2.ORDER_STATE_WORKING,
                        instrument=wo.instrument,
                        action=wo.action,
                        leaves_qty=wo.quantity,
                        correlation_id=mo.correlation_id,
                        timestamp_unix_ms=int(time.time() * 1000),
                        rejection_reason="modified",
                    )
                )
                continue

            if which == "flatten":
                self.working.clear()
                yield fabric_pb2.FabricMessage(
                    order_event=fabric_pb2.OrderEvent(
                        client_order_id="flatten",
                        nt_order_id="flat-1",
                        state=fabric_pb2.ORDER_STATE_SUBMITTED,
                        correlation_id=msg.flatten.correlation_id,
                        timestamp_unix_ms=int(time.time() * 1000),
                    )
                )

    def GetAccountState(self, request, context):  # noqa: N802, ANN001
        return fabric_pb2.AccountState(
            account=fabric_pb2.AccountMetrics(
                balance=100_000.0,
                equity=100_000.0,
                account_name=self.account,
                currency="USD",
            ),
            safe_mode=(
                fabric_pb2.SAFE_MODE_STATE_SAFE if self.safe_mode else fabric_pb2.SAFE_MODE_STATE_NORMAL
            ),
            timestamp_unix_ms=int(time.time() * 1000),
        )

    def RequestHistoricalData(self, request, context):  # noqa: N802, ANN001
        return fabric_pb2.HistoricalDataResponse(code="NOT_IMPLEMENTED", message="mock")

    def SetRiskParameters(self, request, context):  # noqa: N802, ANN001
        return fabric_pb2.RiskParametersAck(accepted=True, applied=request)

    def GetRiskParameters(self, request, context):  # noqa: N802, ANN001
        return fabric_pb2.RiskParameters(heartbeat_timeout_ms=5000)


@pytest.fixture
def chaos_server() -> Iterator[tuple[str, _ChaosFabricServicer]]:
    servicer = _ChaosFabricServicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    fabric_pb2_grpc.add_ExecutionFabricServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield f"127.0.0.1:{port}", servicer
    finally:
        server.stop(grace=1)


def _client(target: str) -> FabricGrpcClient:
    host, port_s = target.split(":")
    return FabricGrpcClient(
        FabricConfig(
            host=host,
            port=int(port_s),
            auth_token="chaos-token",
            heartbeat_interval_ms=0,
            connect_timeout_seconds=3.0,
            command_timeout_seconds=3.0,
        )
    )


def test_idempotent_duplicate_client_order_id(chaos_server: tuple[str, _ChaosFabricServicer]) -> None:
    target, servicer = chaos_server
    client = _client(target)
    assert client.connect() is True
    cid = "idem-" + uuid.uuid4().hex[:8]
    order = Order(symbol="MNQ", side="BUY", quantity=1, order_type="MARKET")
    r1 = client.place_order_sync(order, client_order_id=cid, correlation_id="c1")
    r2 = client.place_order_sync(order, client_order_id=cid, correlation_id="c2")
    assert r1["type"] == "ack"
    assert r2["type"] == "ack"
    assert r1["order_id"] == r2["order_id"]
    # Only one real place after first; second is replay (servicer place_count still 2 loops but idempotent store)
    assert servicer.place_count >= 1
    client.disconnect()


def test_safe_mode_rejects_new_orders(chaos_server: tuple[str, _ChaosFabricServicer]) -> None:
    target, servicer = chaos_server
    client = _client(target)
    assert client.connect() is True
    servicer.safe_mode = True
    r = client.place_order_sync(
        Order(symbol="MNQ", side="BUY", quantity=1, order_type="MARKET"),
        client_order_id="safe-block-1",
        correlation_id="sc1",
    )
    assert r["type"] == "error"
    assert "SAFE" in str(r.get("code", "")).upper() or "safe" in str(r.get("message", "")).lower()
    client.disconnect()


def test_modify_limit_order(chaos_server: tuple[str, _ChaosFabricServicer]) -> None:
    target, _servicer = chaos_server
    client = _client(target)
    assert client.connect() is True
    cid = "lim-" + uuid.uuid4().hex[:8]
    order = Order(symbol="MNQ", side="BUY", quantity=2, order_type="LIMIT")
    order.metadata["price"] = 20950.0
    r = client.place_order_sync(order, client_order_id=cid, correlation_id="m1")
    assert r["type"] == "ack"
    mod = client.modify_order_sync(client_order_id=cid, quantity=3, price=20960.0, correlation_id="m2")
    assert mod["type"] == "ack"
    assert mod.get("state") == fabric_pb2.ORDER_STATE_WORKING
    client.disconnect()


def test_disconnect_fail_closed_on_bridge(chaos_server: tuple[str, _ChaosFabricServicer]) -> None:
    target, _servicer = chaos_server
    host, port_s = target.split(":")
    bridge = NinjaTraderBridgeService(
        configured_account="Sim101",
        trade_mode="sim",
        ninjatrader_enabled=True,
        command_timeout_seconds=3.0,
    )
    client = FabricGrpcClient(
        FabricConfig(
            host=host,
            port=int(port_s),
            auth_token="chaos-token",
            heartbeat_interval_ms=0,
            connect_timeout_seconds=3.0,
            command_timeout_seconds=3.0,
        )
    )
    bridge.attach_fabric_client(client)
    assert bridge.connect_fabric() is True
    assert bridge.get_last_state_hash() == "deadbeefcafebabe" or bridge.get_connection_state().is_connected

    # Allow state_sync to be applied asynchronously.
    deadline = time.time() + 2.0
    while time.time() < deadline and not bridge.get_last_state_hash():
        time.sleep(0.05)
    assert bridge.get_last_state_hash() == "deadbeefcafebabe"

    bridge.on_disconnect()
    resp = bridge.send_command_sync(
        {
            "type": "submit_order",
            "symbol": "MNQ",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "client_order_id": "after-disc",
        }
    )
    assert resp["type"] == "error"


def test_safety_alert_marks_bridge_degraded(chaos_server: tuple[str, _ChaosFabricServicer]) -> None:
    target, _servicer = chaos_server
    host, port_s = target.split(":")
    bridge = NinjaTraderBridgeService(
        configured_account="Sim101",
        trade_mode="sim",
        ninjatrader_enabled=True,
    )
    client = FabricGrpcClient(
        FabricConfig(host=host, port=int(port_s), auth_token="chaos-token", heartbeat_interval_ms=0)
    )
    bridge.attach_fabric_client(client)
    assert bridge.connect_fabric() is True

    # Inject a safety alert as if Fabric broadcast it.
    alert_msg = fabric_pb2.FabricMessage(
        safety_alert=fabric_pb2.SafetyAlert(
            alert_type=fabric_pb2.SAFETY_ALERT_TYPE_HEARTBEAT_TIMEOUT,
            severity=fabric_pb2.SAFETY_SEVERITY_CRITICAL,
            message="simulated timeout",
            recommended_action="cancel_and_safe_mode",
            timestamp_unix_ms=int(time.time() * 1000),
        )
    )
    bridge._on_fabric_message(alert_msg)  # noqa: SLF001 — intentional unit injection
    state = bridge.get_connection_state()
    assert state.state == "degraded"
    assert not state.allows_new_orders
    alerts = bridge.get_safety_alerts()
    assert len(alerts) >= 1
    assert "timeout" in alerts[-1]["message"]
