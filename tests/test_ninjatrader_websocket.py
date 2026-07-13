from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

_LUMINA_OS_PATH = Path(__file__).resolve().parents[1] / "lumina_os"
if str(_LUMINA_OS_PATH) not in sys.path:
    sys.path.insert(0, str(_LUMINA_OS_PATH))

from backend.ninjatrader_websocket import router as ninjatrader_router  # noqa: E402
from lumina_core.broker.ninjatrader.bridge_service import reset_ninjatrader_bridge_service  # noqa: E402
from lumina_core.broker.ninjatrader.broker import NinjaTraderBroker  # noqa: E402
from lumina_core.broker.broker_bridge.schemas import Order  # noqa: E402


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@pytest.fixture(autouse=True)
def _reset_bridge() -> None:
    reset_ninjatrader_bridge_service()
    yield
    reset_ninjatrader_bridge_service()


@pytest.fixture
def ws_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("LUMINA_NT8_API_KEY", "test-nt8-key")
    monkeypatch.setattr(
        "backend.ninjatrader_websocket.ConfigLoader.get",
        classmethod(
            lambda cls: {
                "mode": "sim",
                "broker": {
                    "live_provider": "ninjatrader",
                    "ninjatrader": {"enabled": True, "account_name": "Sim101"},
                },
            }
        ),
    )
    app = FastAPI()
    app.include_router(ninjatrader_router)
    return TestClient(app)


def test_ws_auth_ok(ws_client: TestClient) -> None:
    correlation_id = str(uuid.uuid4())
    with ws_client.websocket_connect("/ws/ninjatrader/v1") as ws:
        ws.send_json(
            {
                "schema_version": "1.0",
                "type": "auth",
                "correlation_id": correlation_id,
                "ts": _utc_now_iso(),
                "token": "test-nt8-key",
                "client": {"name": "test", "version": "0.1.0"},
            }
        )
        frame = ws.receive_json()
        assert frame["type"] == "auth_ok"
        assert frame["correlation_id"] == correlation_id


def test_ws_auth_invalid_closes(ws_client: TestClient) -> None:
    with ws_client.websocket_connect("/ws/ninjatrader/v1") as ws:
        ws.send_json(
            {
                "schema_version": "1.0",
                "type": "auth",
                "correlation_id": str(uuid.uuid4()),
                "ts": _utc_now_iso(),
                "token": "bad-key",
                "client": {"name": "test", "version": "0.1.0"},
            }
        )
        frame = ws.receive_json()
        assert frame["type"] == "auth_failed"
    # Connection closes after auth_failed (4401) — context manager exits cleanly.


def test_ws_ping_pong(ws_client: TestClient) -> None:
    with ws_client.websocket_connect("/ws/ninjatrader/v1") as ws:
        ws.send_json(
            {
                "schema_version": "1.0",
                "type": "auth",
                "correlation_id": str(uuid.uuid4()),
                "ts": _utc_now_iso(),
                "token": "test-nt8-key",
                "client": {"name": "test", "version": "0.1.0"},
            }
        )
        ws.receive_json()
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_fill_deduplication(ws_client: TestClient) -> None:
    from lumina_core.broker.ninjatrader.bridge_service import get_ninjatrader_bridge_service

    with ws_client.websocket_connect("/ws/ninjatrader/v1") as ws:
        ws.send_json(
            {
                "schema_version": "1.0",
                "type": "auth",
                "correlation_id": str(uuid.uuid4()),
                "ts": _utc_now_iso(),
                "token": "test-nt8-key",
                "client": {"name": "test", "version": "0.1.0"},
            }
        )
        ws.receive_json()
        execution = {
            "schema_version": "1.0",
            "type": "execution",
            "correlation_id": str(uuid.uuid4()),
            "ts": _utc_now_iso(),
            "execution_id": "exec-1",
            "order_id": "ord-1",
            "client_order_id": "coid-1",
            "symbol": "MES 06-26",
            "side": "BUY",
            "quantity": 1,
            "price": 5240.25,
        }
        ws.send_json(execution)
        ws.send_json(execution)

    bridge = get_ninjatrader_bridge_service()
    fills = bridge.get_fills()
    assert len(fills) == 1
    assert fills[0].fill_id == "exec-1"


def test_broker_admission_blocks_before_ws_send() -> None:
    from lumina_core.broker.ninjatrader.bridge_service import get_ninjatrader_bridge_service

    bridge = get_ninjatrader_bridge_service(
        configured_account="Sim101",
        trade_mode="sim",
        ninjatrader_enabled=True,
        reset=True,
    )
    bridge.authenticate_session(session_id="sess", account_name="Sim101")

    sent: list[dict] = []

    def _capture_send(frame: dict) -> None:
        sent.append(frame)

    bridge.register_send(_capture_send)

    engine = SimpleNamespace(config=SimpleNamespace(trade_mode="sim"))
    broker = NinjaTraderBroker(
        configured_account="Sim101",
        ninjatrader_enabled=True,
        engine=engine,
        bridge_service=bridge,
    )

    with patch("lumina_core.broker.ninjatrader.broker.run_final_arbitration", return_value=(False, "gate_reject")):
        result = broker.submit_order(
            Order(symbol="MES 06-26", side="BUY", quantity=1, metadata={"reference_price": 100.0, "proposed_risk": 1.0})
        )

    assert result.accepted is False
    assert "FinalArbitration" in result.message
    assert sent == []
