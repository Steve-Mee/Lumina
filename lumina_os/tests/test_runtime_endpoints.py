from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("LUMINA_JWT_SECRET_KEY", "lumina_test_jwt_secret_key_min_len_32")

from backend.app import app  # noqa: E402


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from backend import app as app_module

    monkeypatch.setenv("LUMINA_DASHBOARD_API_KEY", "test-key")

    def _accept_test_key(key: str | None) -> dict[str, str] | None:
        if key == "test-key":
            return {"name": "test", "role": "admin"}
        return None

    monkeypatch.setattr(
        app_module.SECURITY["api_key"],
        "verify_api_key",
        _accept_test_key,
    )
    return TestClient(app)


def test_runtime_status_requires_api_key(client: TestClient) -> None:
    response = client.get("/api/runtime/status")
    assert response.status_code == 401


def test_runtime_start_stop_with_mock_process_manager(client: TestClient) -> None:
    mock_pm = MagicMock()
    mock_pm.is_process_alive.return_value = False
    mock_pm.start_bot.return_value = (True, "started")
    mock_pm.stop_bot.return_value = (True, "stopped")
    mock_pm._load_process_state.return_value = {"pid": 1234, "mode": "sim"}

    with patch("backend.runtime_endpoints._get_process_manager", return_value=mock_pm):
        start = client.post(
            "/api/runtime/start",
            json={"mode": "sim"},
            headers={"X-API-Key": "test-key"},
        )
        assert start.status_code == 200
        assert start.json()["ok"] is True

        mock_pm.is_process_alive.return_value = True
        status = client.get("/api/runtime/status", headers={"X-API-Key": "test-key"})
        assert status.status_code == 200

        stop = client.post("/api/runtime/stop", headers={"X-API-Key": "test-key"})
        assert stop.status_code == 200


def test_runtime_training_pause_resume(client: TestClient, tmp_path: Path) -> None:
    pause_flag = tmp_path / "state" / "first_boot_pause_requested"

    with patch("backend.runtime_endpoints._REPO_ROOT", tmp_path):
        with patch("backend.runtime_endpoints._get_first_boot_manager") as mock_fb:
            manager = MagicMock()
            mock_fb.return_value = manager

            pause = client.post("/api/runtime/training-pause", headers={"X-API-Key": "test-key"})
            assert pause.status_code == 200
            manager.request_pause.assert_called_once()

            resume = client.post("/api/runtime/training-resume", headers={"X-API-Key": "test-key"})
            assert resume.status_code == 200
            manager.clear_pause_request.assert_called_once()


def test_runtime_go_live_requires_ready(client: TestClient) -> None:
    with patch(
        "lumina_core.engine.sim_stability_checker.generate_stability_report",
        return_value={"READY_FOR_REAL": False},
    ):
        response = client.post(
            "/api/runtime/go-live?confirm=true",
            headers={"X-API-Key": "test-key"},
        )
        assert response.status_code == 422


def test_runtime_go_live_writes_env(client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\n", encoding="utf-8")
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")

    with patch("backend.runtime_endpoints._REPO_ROOT", tmp_path):
        with patch(
            "lumina_core.engine.sim_stability_checker.generate_stability_report",
            return_value={"READY_FOR_REAL": True, "consecutive_green_days": 5},
        ):
            response = client.post(
                "/api/runtime/go-live?confirm=true",
                headers={"X-API-Key": "test-key"},
            )
            assert response.status_code == 200
            assert "LUMINA_MODE=real" in env_path.read_text(encoding="utf-8")


def test_runtime_stop_all(client: TestClient) -> None:
    mock_pm = MagicMock()
    mock_pm.stop_all_activities.return_value = (True, "All stopped")

    with patch("backend.runtime_endpoints._get_process_manager", return_value=mock_pm):
        with patch("backend.app._execute_cancel_all_orders", return_value={"cancelled_count": 0}):
            with patch("backend.app._execute_emergency_flatten", return_value={"flattened_count": 0}):
                response = client.post("/api/runtime/stop-all", headers={"X-API-Key": "test-key"})
                assert response.status_code == 200
                assert response.json()["ok"] is True
                mock_pm.stop_all_activities.assert_called_once()
