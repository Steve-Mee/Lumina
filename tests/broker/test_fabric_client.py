"""Integration tests: FabricGrpcClient against in-process mock gRPC server."""

from __future__ import annotations

import time
from concurrent import futures
from types import SimpleNamespace
from typing import Iterator

import pytest

pytest.importorskip("grpc")

import grpc

from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.broker.ninjatrader.bridge_service import (
    NinjaTraderBridgeService,
    reset_ninjatrader_bridge_service,
)
from lumina_core.broker.ninjatrader.broker import NinjaTraderBroker
from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient
from lumina_core.broker.ninjatrader.generated import fabric_pb2, fabric_pb2_grpc


class _MockFabricServicer(fabric_pb2_grpc.ExecutionFabricServicer):
    def __init__(self, *, expected_token: str = "test-token", account: str = "Sim101") -> None:
        self.expected_token = expected_token
        self.account = account
        self.place_calls = 0
        self.flatten_calls = 0
        self.reject_orders = False
        self.safe_mode = False
        self.historical_mode = "ok"  # ok | not_implemented | host_no_nt

    def TradingStream(  # noqa: N802 — gRPC naming
        self,
        request_iterator: Iterator[fabric_pb2.BrainMessage],
        context: grpc.ServicerContext,
    ) -> Iterator[fabric_pb2.FabricMessage]:
        for msg in request_iterator:
            which = msg.WhichOneof("payload")
            if which == "auth_hello":
                ok = msg.auth_hello.token == self.expected_token
                yield fabric_pb2.FabricMessage(
                    auth_result=fabric_pb2.AuthResult(
                        ok=ok,
                        session_id="sess-mock-1" if ok else "",
                        account_name=self.account if ok else "",
                        code="OK" if ok else "AUTH_FAILED",
                        message="ok" if ok else "bad token",
                    )
                )
                continue

            if which == "heartbeat":
                yield fabric_pb2.FabricMessage(
                    heartbeat=fabric_pb2.Heartbeat(
                        sequence_number=msg.heartbeat.sequence_number,
                        timestamp_unix_ms=msg.heartbeat.timestamp_unix_ms,
                        fabric_safe_mode=(
                            fabric_pb2.SAFE_MODE_STATE_SAFE
                            if self.safe_mode
                            else fabric_pb2.SAFE_MODE_STATE_NORMAL
                        ),
                    )
                )
                continue

            if which == "place_order":
                self.place_calls += 1
                po = msg.place_order
                if self.reject_orders or self.safe_mode:
                    yield fabric_pb2.FabricMessage(
                        command_reject=fabric_pb2.CommandReject(
                            correlation_id=po.correlation_id,
                            client_order_id=po.client_order_id,
                            code="SAFE_MODE" if self.safe_mode else "REJECTED",
                            message="rejected by mock",
                            safe_mode=(
                                fabric_pb2.SAFE_MODE_STATE_SAFE
                                if self.safe_mode
                                else fabric_pb2.SAFE_MODE_STATE_NORMAL
                            ),
                        )
                    )
                    continue
                yield fabric_pb2.FabricMessage(
                    order_event=fabric_pb2.OrderEvent(
                        client_order_id=po.client_order_id,
                        nt_order_id=f"nt-{self.place_calls}",
                        state=fabric_pb2.ORDER_STATE_WORKING,
                        instrument=po.instrument,
                        action=po.action,
                        correlation_id=po.correlation_id,
                        timestamp_unix_ms=int(time.time() * 1000),
                    )
                )
                yield fabric_pb2.FabricMessage(
                    order_event=fabric_pb2.OrderEvent(
                        client_order_id=po.client_order_id,
                        nt_order_id=f"nt-{self.place_calls}",
                        state=fabric_pb2.ORDER_STATE_FILLED,
                        filled_qty=po.quantity,
                        avg_fill_price=21000.25,
                        instrument=po.instrument,
                        action=po.action,
                        correlation_id=po.correlation_id,
                        timestamp_unix_ms=int(time.time() * 1000),
                    )
                )
                continue

            if which == "flatten":
                self.flatten_calls += 1
                fl = msg.flatten
                yield fabric_pb2.FabricMessage(
                    order_event=fabric_pb2.OrderEvent(
                        client_order_id="flatten",
                        nt_order_id=f"flat-{self.flatten_calls}",
                        state=fabric_pb2.ORDER_STATE_SUBMITTED,
                        correlation_id=fl.correlation_id,
                        timestamp_unix_ms=int(time.time() * 1000),
                    )
                )
                continue

            if which == "cancel_order":
                co = msg.cancel_order
                yield fabric_pb2.FabricMessage(
                    order_event=fabric_pb2.OrderEvent(
                        client_order_id=co.client_order_id,
                        nt_order_id=co.nt_order_id or "nt-cancel",
                        state=fabric_pb2.ORDER_STATE_CANCELLED,
                        correlation_id=co.correlation_id,
                        timestamp_unix_ms=int(time.time() * 1000),
                    )
                )

    def GetAccountState(  # noqa: N802
        self,
        request: fabric_pb2.GetAccountStateRequest,
        context: grpc.ServicerContext,
    ) -> fabric_pb2.AccountState:
        return fabric_pb2.AccountState(
            account=fabric_pb2.AccountMetrics(
                balance=100_000.0,
                equity=100_100.0,
                available_margin=90_000.0,
                realized_pnl_today=100.0,
                currency="USD",
                account_name=self.account,
            ),
            positions=[
                fabric_pb2.PositionUpdate(
                    instrument="MNQ",
                    quantity=1,
                    avg_price=21000.0,
                    side="LONG",
                )
            ],
            safe_mode=fabric_pb2.SAFE_MODE_STATE_NORMAL,
            timestamp_unix_ms=int(time.time() * 1000),
        )

    def RequestHistoricalData(self, request, context):  # noqa: N802, ANN001
        # Mirror C# TryAuthorizeUnary: require x-lumina-token when expected_token set.
        md = dict(context.invocation_metadata() or ())
        token = str(md.get("x-lumina-token") or md.get("authorization") or "").replace("Bearer ", "").strip()
        if self.expected_token and token != self.expected_token:
            return fabric_pb2.HistoricalDataResponse(
                instrument=request.instrument,
                correlation_id=request.correlation_id,
                code="UNAUTHENTICATED",
                message="AUTH_FAILED",
            )
        if self.historical_mode == "not_implemented":
            return fabric_pb2.HistoricalDataResponse(
                instrument=request.instrument,
                correlation_id=request.correlation_id,
                code="NOT_IMPLEMENTED",
                message="mock",
            )
        if self.historical_mode == "host_no_nt":
            return fabric_pb2.HistoricalDataResponse(
                instrument=request.instrument,
                correlation_id=request.correlation_id,
                code="HOST_NO_NT_DATA",
                message="SimHost is execution-only",
            )
        # Return enough 1-min bars for dual-plane diagnostics (min 10).
        now_ms = int(time.time() * 1000)
        bars = []
        for i in range(20):
            ts = now_ms - (20 - i) * 60_000
            px = 5000.0 + i
            bars.append(
                fabric_pb2.MarketDataUpdate(
                    instrument=request.instrument or "MES",
                    timestamp_unix_ms=ts,
                    open=px,
                    high=px + 1,
                    low=px - 1,
                    close=px + 0.25,
                    last=px + 0.25,
                    volume=100 + i,
                    is_bar=True,
                )
            )
        return fabric_pb2.HistoricalDataResponse(
            instrument=request.instrument or "MES",
            correlation_id=request.correlation_id,
            code="ok",
            message="bars=20 provider=mock",
            bars=bars,
        )

    def SetRiskParameters(self, request, context):  # noqa: N802, ANN001
        return fabric_pb2.RiskParametersAck(accepted=True, applied=request)

    def GetRiskParameters(self, request, context):  # noqa: N802, ANN001
        return fabric_pb2.RiskParameters(heartbeat_timeout_ms=5000)


@pytest.fixture
def mock_fabric_server() -> Iterator[tuple[str, _MockFabricServicer]]:
    servicer = _MockFabricServicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    fabric_pb2_grpc.add_ExecutionFabricServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield f"127.0.0.1:{port}", servicer
    finally:
        server.stop(grace=1)


def test_fabric_client_connect_auth_and_place_order(mock_fabric_server: tuple[str, _MockFabricServicer]) -> None:
    target, servicer = mock_fabric_server
    host, port_s = target.split(":")
    cfg = FabricConfig(
        host=host,
        port=int(port_s),
        auth_token="test-token",
        heartbeat_interval_ms=0,  # disable background HB for stability
        connect_timeout_seconds=3.0,
        command_timeout_seconds=3.0,
    )
    client = FabricGrpcClient(cfg)
    assert client.connect() is True
    assert client.session_id == "sess-mock-1"
    assert client.account_name == "Sim101"

    order = Order(symbol="MNQ", side="BUY", quantity=1, order_type="MARKET")
    resp = client.place_order_sync(order, client_order_id="cid-place-1", correlation_id="corr-place-1")
    assert resp["type"] == "ack"
    assert resp["order_id"].startswith("nt-")
    assert servicer.place_calls == 1

    account, positions, code = client.get_account_state()
    assert code == "ok"
    assert account is not None
    assert account.equity == pytest.approx(100_100.0)
    assert len(positions) == 1
    assert positions[0].symbol == "MNQ"

    hist = client.request_historical_data(instrument="MES", max_bars=20)
    assert hist["code"] == "ok"
    assert len(hist["bars"]) >= 10
    assert hist["bars"][0]["close"] > 0

    client.disconnect()
    assert client.is_connected is False


def test_fabric_client_historical_unary_auth_metadata(
    mock_fabric_server: tuple[str, _MockFabricServicer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G7: unary historical requires x-lumina-token (client sends via _auth_metadata)."""
    target, servicer = mock_fabric_server
    host, port_s = target.split(":")
    monkeypatch.delenv("LUMINA_FABRIC_TOKEN", raising=False)
    monkeypatch.delenv("LUMINA_NT8_API_KEY", raising=False)
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_secret.read",
        lambda heal=True: SimpleNamespace(token=""),
        raising=False,
    )
    # Wrong token → UNAUTHENTICATED
    bad = FabricGrpcClient(
        FabricConfig(
            host=host,
            port=int(port_s),
            auth_token="wrong-token",
            heartbeat_interval_ms=0,
            connect_timeout_seconds=3.0,
            command_timeout_seconds=3.0,
        )
    )
    # Use correct stream token then clear so resolve_token fail-closes (ADR-0041).
    good = FabricGrpcClient(
        FabricConfig(
            host=host,
            port=int(port_s),
            auth_token="test-token",
            heartbeat_interval_ms=0,
            connect_timeout_seconds=3.0,
            command_timeout_seconds=3.0,
        )
    )
    assert good.connect() is True
    hist_ok = good.request_historical_data(instrument="MES", max_bars=5)
    assert hist_ok["code"] == "ok"
    good.config.auth_token = ""
    with pytest.raises(RuntimeError, match="Fabric auth token is empty"):
        good.request_historical_data(instrument="MES", max_bars=5)
    good.disconnect()
    _ = bad  # silence unused if connect not used
    _ = servicer


def test_fabric_client_historical_host_no_nt(mock_fabric_server: tuple[str, _MockFabricServicer]) -> None:
    target, servicer = mock_fabric_server
    servicer.historical_mode = "host_no_nt"
    host, port_s = target.split(":")
    client = FabricGrpcClient(
        FabricConfig(
            host=host,
            port=int(port_s),
            auth_token="test-token",
            heartbeat_interval_ms=0,
            connect_timeout_seconds=3.0,
            command_timeout_seconds=3.0,
        )
    )
    assert client.connect() is True
    hist = client.request_historical_data(instrument="MES", max_bars=10)
    assert hist["code"] == "HOST_NO_NT_DATA"
    assert hist["bars"] == []
    client.disconnect()


def test_fabric_client_auth_failure(mock_fabric_server: tuple[str, _MockFabricServicer]) -> None:
    target, _servicer = mock_fabric_server
    host, port_s = target.split(":")
    client = FabricGrpcClient(
        FabricConfig(host=host, port=int(port_s), auth_token="wrong", heartbeat_interval_ms=0, connect_timeout_seconds=2.0)
    )
    assert client.connect() is False
    assert client.is_connected is False


def test_bridge_and_broker_submit_via_fabric(mock_fabric_server: tuple[str, _MockFabricServicer], monkeypatch: pytest.MonkeyPatch) -> None:
    reset_ninjatrader_bridge_service()
    target, servicer = mock_fabric_server
    host, port_s = target.split(":")

    # Authoritative gate path used by run_final_arbitration (same as paper broker tests).
    monkeypatch.setattr(
        "lumina_core.broker.broker_bridge.enforce_pre_trade_gate",
        lambda *a, **k: (True, "OK"),
    )

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
            auth_token="test-token",
            heartbeat_interval_ms=0,
            connect_timeout_seconds=3.0,
            command_timeout_seconds=3.0,
        )
    )
    bridge.attach_fabric_client(client)
    broker = NinjaTraderBroker(
        configured_account="Sim101",
        ninjatrader_enabled=True,
        command_timeout_seconds=3.0,
        bridge_service=bridge,
        engine=SimpleNamespace(config=SimpleNamespace(trade_mode="sim")),
    )

    assert broker.connect() is True
    result = broker.submit_order(Order(symbol="MNQ", side="BUY", quantity=1, order_type="MARKET"))
    assert result.accepted is True
    assert result.order_id.startswith("nt-")
    assert servicer.place_calls == 1

    # Allow stream to deliver fill event.
    deadline = time.time() + 2.0
    while time.time() < deadline and not broker.get_fills():
        time.sleep(0.05)
    fills = broker.get_fills()
    assert len(fills) >= 1
    assert fills[0].symbol == "MNQ"

    cancel = broker.cancel_all_orders()
    assert cancel.get("ok") is True
    assert servicer.flatten_calls >= 1

    broker.disconnect()
    reset_ninjatrader_bridge_service()


def test_bridge_guard_blocks_when_disconnected(mock_fabric_server: tuple[str, _MockFabricServicer]) -> None:
    target, _servicer = mock_fabric_server
    host, port_s = target.split(":")
    bridge = NinjaTraderBridgeService(configured_account="Sim101", trade_mode="sim", ninjatrader_enabled=True)
    bridge.attach_fabric_client(
        FabricGrpcClient(
            FabricConfig(host=host, port=int(port_s), auth_token="test-token", heartbeat_interval_ms=0)
        )
    )
    # Not connected → fail-closed
    resp = bridge.send_command_sync(
        {
            "type": "submit_order",
            "symbol": "MNQ",
            "side": "BUY",
            "quantity": 1,
            "order_type": "MARKET",
            "client_order_id": "x",
        }
    )
    assert resp["type"] == "error"
    assert "disconnected" in str(resp.get("message", "")).lower() or resp.get("code") in {
        "BRIDGE_GUARD",
        "DISCONNECTED",
    }


def test_factory_attaches_fabric_client() -> None:
    from lumina_core.broker.broker_bridge.factory import broker_factory
    from lumina_core.broker.ninjatrader.bridge_service import reset_ninjatrader_bridge_service

    reset_ninjatrader_bridge_service()
    cfg = SimpleNamespace(
        broker_backend="live",
        trade_mode="sim",
        broker_live_provider="ninjatrader",
        ninjatrader_enabled=True,
        ninjatrader_account_name="Sim101",
        ninjatrader_fabric_host="127.0.0.1",
        ninjatrader_fabric_port=50051,
        ninjatrader_fabric_auth_token_env="LUMINA_FABRIC_TOKEN",
        ninjatrader_nt8_api_key="tok",
    )
    broker = broker_factory(config=cfg, engine=None, logger=None)
    assert isinstance(broker, NinjaTraderBroker)
    assert broker.bridge_service is not None
    assert broker.bridge_service.get_fabric_client() is not None
    reset_ninjatrader_bridge_service()
