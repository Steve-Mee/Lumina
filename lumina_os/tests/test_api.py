from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ["TRADER_LEAGUE_DATABASE_URL"] = f"sqlite:///{Path(__file__).parent / 'test_trader_league.db'}"
os.environ["TRADER_LEAGUE_RECONCILIATION_STATUS_FILE"] = str(Path(__file__).parent / "test_reconciliation_status.json")
_prev_jwt_secret = os.environ.get("LUMINA_JWT_SECRET_KEY")
os.environ["LUMINA_JWT_SECRET_KEY"] = "lumina_test_jwt_secret_key_min_len_32"

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import app  # noqa: E402

if _prev_jwt_secret is None:
    os.environ.pop("LUMINA_JWT_SECRET_KEY", None)
else:
    os.environ["LUMINA_JWT_SECRET_KEY"] = _prev_jwt_secret

client = TestClient(app)


def test_create_trade_and_list_trades() -> None:
    client.delete("/trades")

    payload = {
        "participant": "TEST_BOT",
        "mode": "paper",
        "symbol": "NQ",
        "signal": "long",
        "entry": 18000.0,
        "exit": 18025.0,
        "qty": 1,
        "pnl": 500.0,
        "broker_fill_id": "fill-001",
        "commission": 1.5,
        "slippage_points": -0.25,
        "fill_latency_ms": 120.0,
        "reconciliation_status": "reconciled_fill",
        "reflection": {"note": "clean setup"},
        "chart_base64": None,
    }

    response = client.post("/trades", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["trade_id"], int)

    trades_response = client.get("/trades?limit=10&participant=TEST_BOT")
    assert trades_response.status_code == 200
    trades = trades_response.json()
    assert len(trades) >= 1
    assert trades[0]["participant"] == "TEST_BOT"
    assert trades[0]["broker_fill_id"] == "fill-001"
    assert trades[0]["commission"] == 1.5
    assert trades[0]["reconciliation_status"] == "reconciled_fill"


def test_leaderboard_contains_participant() -> None:
    payload = {
        "participant": "TEST_ALPHA",
        "mode": "paper",
        "symbol": "ES",
        "signal": "short",
        "entry": 5300.0,
        "exit": 5290.0,
        "qty": 1,
        "pnl": 100.0,
        "reflection": {"note": "test trade"},
        "chart_base64": None,
    }
    response = client.post("/trades", json=payload)
    assert response.status_code == 200

    leaderboard_response = client.get("/leaderboard")
    assert leaderboard_response.status_code == 200
    body = leaderboard_response.json()
    assert "leaderboard" in body
    assert any(row["participant"] == "TEST_ALPHA" for row in body["leaderboard"])


def test_demo_data_cleanup_endpoint() -> None:
    payload = {
        "participant": "DEMO_FOR_TEST",
        "mode": "paper",
        "symbol": "CL",
        "signal": "long",
        "entry": 80.0,
        "exit": 80.5,
        "qty": 1,
        "pnl": 50.0,
        "reflection": {"note": "demo cleanup"},
        "chart_base64": None,
    }
    response = client.post("/trades", json=payload)
    assert response.status_code == 200

    cleanup_response = client.delete(
        "/demo-data",
        headers={"X-API-Key": "sk_example_admin_key_replace_me"},
    )
    assert cleanup_response.status_code == 200
    cleanup = cleanup_response.json()
    assert cleanup["deleted_participants"] >= 1


def test_reconciliation_status_endpoint_reads_status_file() -> None:
    status_path = Path(os.environ["TRADER_LEAGUE_RECONCILIATION_STATUS_FILE"])
    status_path.write_text(
        '{"method":"websocket","connection_state":"connected","pending_count":2,"pending_symbols":["MES JUN26"],"updated_at":"2026-04-05T12:00:00+00:00"}',
        encoding="utf-8",
    )

    response = client.get("/reconciliation-status")
    assert response.status_code == 200
    body = response.json()
    assert body["connection_state"] == "connected"
    assert body["pending_count"] == 2


def test_upload_reflection_without_suggested_update_is_accepted() -> None:
    bible_payload = {
        "trader_name": "LUMINA_Steve",
        "evolvable_layer": {"rule": "volume_first"},
        "backtest_results": {"sharpe": 1.8},
    }
    bible_response = client.post("/upload/bible", json=bible_payload)
    assert bible_response.status_code == 200

    reflection_payload = {
        "trader_name": "LUMINA_Steve",
        "reflection": "Perfect tape reading",
        "key_lesson": "Volume is king",
    }
    reflection_response = client.post("/upload/reflection", json=reflection_payload)
    assert reflection_response.status_code == 200
    assert reflection_response.json().get("status") == "ok"
