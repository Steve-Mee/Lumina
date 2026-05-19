from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault(
    "TRADER_LEAGUE_DATABASE_URL",
    f"sqlite:///{Path(__file__).parent / 'test_trader_league.db'}",
)
os.environ.setdefault(
    "TRADER_LEAGUE_RECONCILIATION_STATUS_FILE",
    str(Path(__file__).parent / "test_reconciliation_status.json"),
)
os.environ.setdefault("LUMINA_JWT_SECRET_KEY", "lumina_test_jwt_secret_key_min_len_32")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app import app  # noqa: E402
from backend.core_websocket import CoreLiveTelemetryReader  # noqa: E402
from backend import core_websocket as core_ws_module  # noqa: E402


@pytest.fixture(autouse=True)
def reset_operator_mode_override() -> None:
    core_ws_module._operator_mode_override = None
    yield
    core_ws_module._operator_mode_override = None


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    sd = tmp_path / "state"
    sd.mkdir()
    (sd / "monitoring_runtime_metrics.json").write_text(
        json.dumps(
            {
                "timestamp": "2026-05-19T12:00:00Z",
                "mode": "sim",
                "account_equity": 100_000.0,
                "consecutive_losses": 0,
            }
        ),
        encoding="utf-8",
    )
    (sd / "evolution_log.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "status": "proposed",
                        "hash": "abc123",
                        "timestamp": "2026-05-19T11:00:00Z",
                        "challengers": [{"name": "alpha"}, {"name": "beta"}],
                    }
                ),
                json.dumps(
                    {
                        "status": "approved",
                        "hash": "def456",
                        "timestamp": "2026-05-19T10:00:00Z",
                        "challengers": [],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return sd


def test_core_live_telemetry_reader_builds_snapshot(state_dir: Path) -> None:
    reader = CoreLiveTelemetryReader(state_dir=state_dir)
    payload = reader.build_snapshot(obs=None)

    assert payload["mode"] == "sim"
    assert payload["equity"] == 100_000.0
    assert payload["risk_level"] == "NORMAL"
    assert len(payload["active_mutations"]) == 1
    assert payload["active_mutations"][0]["hash"] == "abc123"
    assert payload["active_mutations"][0]["challenger_count"] == 2


def test_get_core_live_returns_telemetry(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )
    monkeypatch.setenv("EVOLUTION_LOG_PATH", str(state_dir / "evolution_log.jsonl"))

    client = TestClient(app)
    response = client.get("/api/core/live")
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "telemetry"
    assert body["seq"] == 0
    assert body["payload"]["mode"] == "sim"
    assert body["payload"]["equity"] == 100_000.0
    assert body["payload"]["active_mutations"][0]["hash"] == "abc123"


def test_ws_core_live_streams_telemetry(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )
    monkeypatch.setenv("EVOLUTION_LOG_PATH", str(state_dir / "evolution_log.jsonl"))

    client = TestClient(app)
    with client.websocket_connect("/ws/core/live") as ws:
        first = ws.receive_json()
        assert first["type"] == "telemetry"
        assert first["seq"] == 0
        assert first["payload"]["mode"] == "sim"
        assert first["payload"]["equity"] == 100_000.0
        assert first["payload"]["active_mutations"][0]["hash"] == "abc123"

        second = ws.receive_json()
        assert second["type"] == "telemetry"
        assert second["seq"] == 1


def test_ws_core_live_responds_to_ping(state_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )
    monkeypatch.setenv("EVOLUTION_LOG_PATH", str(state_dir / "evolution_log.jsonl"))

    client = TestClient(app)
    with client.websocket_connect("/ws/core/live") as ws:
        ws.receive_json()
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"
        assert "ts" in pong


def test_post_core_mode_updates_live_telemetry(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )
    monkeypatch.setenv("EVOLUTION_LOG_PATH", str(state_dir / "evolution_log.jsonl"))

    client = TestClient(app)
    response = client.post("/api/core/mode", json={"mode": "real"})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "mode": "real"}

    live = client.get("/api/core/live")
    assert live.status_code == 200
    assert live.json()["payload"]["mode"] == "real"


def test_post_core_mode_rejects_invalid_mode(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "backend.core_websocket.resolve_state_directory",
        lambda: state_dir,
    )

    client = TestClient(app)
    response = client.post("/api/core/mode", json={"mode": "paper"})
    assert response.status_code == 422
