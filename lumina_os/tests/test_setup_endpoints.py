"""Tests for setup/onboarding endpoints and step computation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend import setup_endpoints as se
from lumina_launcher.core.onboarding import compute_onboarding_steps, should_skip_wizard


@pytest.mark.unit
def test_compute_onboarding_steps_fresh_install() -> None:
    required, status = compute_onboarding_steps(
        backend_reachable=True,
        setup_complete=False,
        intelligence_missing=["ollama", "model:qwen3.5:4b"],
        credentials_missing=["LUMINA_JWT_SECRET_KEY"],
        birth_status="idle",
        artifacts_ok=False,
    )
    assert "welcome" in required
    assert "credentials" in required
    assert "configuration" in required
    assert status["credentials"] == "pending"
    assert status["ollama"] == "pending"


@pytest.mark.unit
def test_compute_onboarding_steps_ready_for_birth() -> None:
    required, status = compute_onboarding_steps(
        backend_reachable=True,
        setup_complete=True,
        intelligence_missing=[],
        credentials_missing=[],
        birth_status="idle",
        artifacts_ok=False,
    )
    assert "birth" in required
    assert status["configuration"] == "done"


@pytest.mark.unit
def test_compute_onboarding_steps_interrupted_birth() -> None:
    required, _status = compute_onboarding_steps(
        backend_reachable=True,
        setup_complete=True,
        intelligence_missing=[],
        credentials_missing=[],
        birth_status="interrupted",
        artifacts_ok=False,
    )
    assert "birth" in required


@pytest.mark.unit
def test_should_skip_wizard_when_birth_running() -> None:
    assert should_skip_wizard(
        setup_complete=True,
        birth_status="running",
        artifacts_ok=False,
        required_steps=["welcome"],
    )


@pytest.mark.unit
def test_should_skip_wizard_when_artifacts_ok() -> None:
    assert should_skip_wizard(
        setup_complete=True,
        birth_status="idle",
        artifacts_ok=True,
        required_steps=["welcome"],
    )


@pytest.mark.unit
@patch.object(se, "birth_service")
@patch.object(se, "_services")
def test_get_onboarding_status(mock_services: MagicMock, mock_birth: MagicMock, tmp_path: Path) -> None:
    setup = MagicMock()
    setup.is_setup_complete.return_value = False
    setup.load_status.return_value = {}
    config_manager = MagicMock()
    config_manager.load_yaml_config.return_value = {
        "mode": "sim",
        "sim": {"kelly_fraction": 1.0},
        "real": {"kelly_fraction": 0.25},
        "evolution": {"approval_required": True},
        "first_boot": {"training_trades": 25000},
        "risk_controller": {"real_capital_safety_threshold_usd": 1000},
    }
    config_manager.parse_env_file.return_value = {}
    smart = MagicMock()
    smart.get_setup_status.return_value = {
        "missing": ["setup_complete", "ollama"],
        "ollama_installed": False,
        "ollama_required": True,
        "recommended_model_key": "qwen3.5:4b",
        "recommended_ollama_tag": "qwen3.5:4b",
        "recommended_model_present": False,
        "recommended_provider": "ollama",
        "hardware": {},
        "adaptive_intelligence": {},
    }
    mock_services.return_value = (setup, config_manager, MagicMock(), smart, MagicMock(), MagicMock())
    mock_birth.workspace_root = tmp_path
    mock_birth.get_status.return_value = {"status": "idle", "message": "not started"}
    mock_birth.artifacts_ok.return_value = False

    with patch.object(se, "_workspace_root", return_value=tmp_path):
        with patch.object(se, "_probe_backend", return_value={"reachable": True, "url": "http://127.0.0.1:8000"}):
            payload = se.build_onboarding_payload()

    assert payload["setup_complete"] is False
    assert "credentials" in payload["required_steps"]
    assert payload["backend"]["reachable"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_start_smart_setup_returns_started() -> None:
    with patch.object(se, "_services") as mock_services:
        mock_services.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock())
        se._smart_setup_running = False
        result = await se.start_smart_setup()
        assert result["status"] == "started"
        se._smart_setup_running = False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_configure_rejects_missing_credentials() -> None:
    setup = MagicMock()
    config_manager = MagicMock()
    config_manager.parse_env_file.return_value = {}
    mock_services = (setup, config_manager, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    with patch.object(se, "_services", return_value=mock_services):
        with patch.object(se, "scan_missing_credentials", return_value=["LUMINA_JWT_SECRET_KEY"]):
            with pytest.raises(Exception) as exc:
                await se.configure_setup(se.ConfigureRequest())
            assert "LUMINA_JWT_SECRET_KEY" in str(exc.value)
