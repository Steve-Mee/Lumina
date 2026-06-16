"""Tests for Birth Phase FastAPI endpoints."""

from __future__ import annotations

import json
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
    assert payload["phase_label"] == "Birth Phase v2"
    assert payload["artifacts_ok"] is False
    assert "Certificate" in payload["artifacts_label"] or "missing" in payload["artifacts_label"].lower()


@pytest.mark.unit
def test_enrich_status_artifacts_ok(_reset_birth_service: MagicMock, tmp_path: Path) -> None:
    _reset_birth_service.workspace_root = tmp_path
    _reset_birth_service.artifacts_ok.return_value = True
    payload = be._enrich_status({"status": "completed"})
    assert payload["artifacts_ok"] is True
    assert "Certificate" in payload["artifacts_label"] or payload["artifacts_label"] == "Birth Certificate v2 OK"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_birth_delegates(_reset_birth_service: MagicMock) -> None:
    result = await be.start_birth(
        target_trades=10000,
        force=False,
        practice_mode=False,
        explicit_user_start=True,
        continue_training=False,
        reuse_data=False,
    )
    _reset_birth_service.start_birth.assert_called_once_with(
        target_trades=10000,
        force=False,
        practice_mode=False,
        explicit_user_start=True,
        continue_training=False,
        reuse_data=False,
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
    assert result["phase_label"] == "Birth Phase v2"
    assert "artifacts_label" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_retry_birth_delegates(_reset_birth_service: MagicMock) -> None:
    _reset_birth_service.retry_birth.return_value = {
        "status": "started",
        "target_trades": 25000,
        "message": "ok",
    }
    _reset_birth_service.get_status.return_value = {
        "status": "running",
        "message": "Birth Phase draait...",
        "progress": {"stage": "detected", "progress_pct": 5},
    }
    result = await be.retry_birth(target_trades=25000, wipe=False)
    _reset_birth_service.retry_birth.assert_called_once_with(target_trades=25000, wipe=False)
    assert result["status"] == "running"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resume_birth_delegates(_reset_birth_service: MagicMock) -> None:
    _reset_birth_service.resume_birth.return_value = {"status": "started", "message": "ok"}
    _reset_birth_service.get_status.return_value = {"status": "running", "progress": {}}
    result = await be.resume_birth(target_trades=25000)
    _reset_birth_service.resume_birth.assert_called_once_with(target_trades=25000)
    assert result["status"] == "running"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_reuse_data_birth_delegates(_reset_birth_service: MagicMock) -> None:
    _reset_birth_service.reuse_data_birth.return_value = {"status": "started", "message": "ok"}
    _reset_birth_service.get_status.return_value = {"status": "running", "progress": {}}
    result = await be.reuse_data_birth(target_trades=25000)
    _reset_birth_service.reuse_data_birth.assert_called_once_with(target_trades=25000)
    assert result["status"] == "running"


@pytest.mark.unit
def test_enrich_status_merges_checkpoint_quality_score(
    _reset_birth_service: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset_birth_service.workspace_root = tmp_path
    ckpt_path = tmp_path / "state" / "lumina_birth_checkpoint.json"
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    ckpt_path.write_text(
        json.dumps(
            {
                "version": 3,
                "quality_score": 72.5,
                "phase": "certificate_failed",
                "data_manifest": {"train_hash": "abc", "preflight_ok": True},
            }
        ),
        encoding="utf-8",
    )
    payload = be._enrich_status({"status": "idle"})
    assert payload["quality_score"] == 72.5
    assert payload["data_manifest"]["train_hash"] == "abc"
    assert payload["checkpoint_phase"] == "certificate_failed"


@pytest.mark.unit
def test_enrich_status_certificate_failed_uses_failure_reasons(
    _reset_birth_service: MagicMock, tmp_path: Path
) -> None:
    _reset_birth_service.workspace_root = tmp_path
    payload = be._enrich_status(
        {
            "status": "certificate_failed",
            "progress": {
                "phase": "certificate_failed",
                "failure_reasons": ["regimes_covered:1/3", "oos_sharpe:0.00/0.35"],
            },
        }
    )
    assert "regimes_covered:1/3" in str(payload["certificate_reason"])
