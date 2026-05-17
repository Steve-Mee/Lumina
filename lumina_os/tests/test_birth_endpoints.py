"""Tests for Birth Phase FastAPI endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend import birth_endpoints as be


@pytest.fixture(autouse=True)
def _reset_birth_service(monkeypatch: pytest.MonkeyPatch) -> Any:
    mock = MagicMock()
    mock.workspace_root = Path(".")
    mock.is_completed.return_value = False
    mock.artifacts_ok.return_value = False
    mock.get_status.return_value = {
        "status": "idle",
        "message": "Birth Phase nog niet gestart",
        "progress": {"trades_done": 0, "target_trades": 25000, "progress_pct": 0, "ppo_steps": 0, "stage": "not_started"},
    }
    mock.start_birth.return_value = {"status": "started", "target_trades": 25000, "message": "ok"}
    mock.stop_birth.return_value = {"status": "stopped", "message": "ok"}
    monkeypatch.setattr(be, "birth_service", mock)
    yield mock


@pytest.mark.unit
def test_enrich_status_artifacts_missing(_reset_birth_service: MagicMock, tmp_path: Path) -> None:
    _reset_birth_service.workspace_root = tmp_path
    payload = be._enrich_status({"status": "idle"})
    assert payload["phase_label"] == "Birth Phase"
    assert payload["artifacts_ok"] is False
    assert payload["artifacts_label"] == "Artifacts missing"


@pytest.mark.unit
def test_enrich_status_artifacts_ok(_reset_birth_service: MagicMock, tmp_path: Path) -> None:
    _reset_birth_service.workspace_root = tmp_path
    _reset_birth_service.artifacts_ok.return_value = True
    payload = be._enrich_status({"status": "completed"})
    assert payload["artifacts_ok"] is True
    assert payload["artifacts_label"] == "Artifacts OK"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_birth_delegates(_reset_birth_service: MagicMock) -> None:
    result = await be.start_birth(
        target_trades=10000,
        force=False,
        practice_mode=False,
        explicit_user_start=True,
        continue_training=False,
    )
    _reset_birth_service.start_birth.assert_called_once_with(
        target_trades=10000,
        force=False,
        practice_mode=False,
        explicit_user_start=True,
        continue_training=False,
    )
    assert result["status"] == "started"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_birth_delegates(_reset_birth_service: MagicMock) -> None:
    result = await be.stop_birth()
    _reset_birth_service.stop_birth.assert_called_once_with()
    assert result["status"] == "stopped"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_birth_status_enriched(_reset_birth_service: MagicMock) -> None:
    result = await be.get_birth_status()
    assert result["phase_label"] == "Birth Phase"
    assert "artifacts_label" in result
