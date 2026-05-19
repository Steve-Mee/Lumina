from __future__ import annotations

import json
import os
import sys
from pathlib import Path

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
from lumina_launcher.services.ppo_realtime import ppo_realtime_tailer  # noqa: E402


@pytest.fixture(autouse=True)
def reset_ppo_tailer(tmp_path: Path, monkeypatch) -> None:
    ppo_realtime_tailer.stop_watching()
    log_path = tmp_path / "state" / "ppo_training_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [{"step": i, "mean_reward": float(i)} for i in range(3)]
    log_path.write_text("\n".join(json.dumps(row) for row in lines) + "\n", encoding="utf-8")
    ppo_realtime_tailer.log_path = log_path
    ppo_realtime_tailer.last_position = log_path.stat().st_size
    ppo_realtime_tailer.clients.clear()
    monkeypatch.setenv("LUMINA_WORKSPACE_ROOT", str(tmp_path))
    yield
    ppo_realtime_tailer.stop_watching()
    ppo_realtime_tailer.clients.clear()


def test_ws_ppo_evolution_sends_recent_history() -> None:
    with TestClient(app) as client:
        with client.websocket_connect("/ws/ppo-evolution") as ws:
            first = ws.receive_text()
            second = ws.receive_text()
            third = ws.receive_text()
            assert json.loads(first)["step"] == 0
            assert json.loads(second)["step"] == 1
            assert json.loads(third)["step"] == 2
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
