"""Tests for setup/onboarding endpoints and step computation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend import setup_endpoints as se
from lumina_launcher.core.onboarding import (
    compute_onboarding_steps,
    resolve_credentials_wizard_meta,
    resolve_wizard_steps,
    should_skip_wizard,
)


@pytest.mark.unit
def test_resolve_wizard_steps_short_path_skips_welcome() -> None:
    assert resolve_wizard_steps(["welcome", "birth"]) == ["birth"]
    assert resolve_wizard_steps(["welcome", "credentials", "birth"]) == [
        "credentials",
        "birth",
    ]


@pytest.mark.unit
def test_resolve_wizard_steps_full_path_keeps_welcome() -> None:
    steps = ["welcome", "ollama", "credentials", "configuration", "birth"]
    assert resolve_wizard_steps(steps) == steps


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
def test_compute_onboarding_steps_skips_credentials_when_setup_complete() -> None:
    required, status = compute_onboarding_steps(
        backend_reachable=True,
        setup_complete=True,
        intelligence_missing=[],
        credentials_missing=["CROSSTRADE_ACCOUNT"],
        birth_status="idle",
        artifacts_ok=False,
    )
    assert "credentials" not in required
    assert status["credentials"] == "done"


@pytest.mark.unit
def test_resolve_credentials_wizard_meta() -> None:
    assert resolve_credentials_wizard_meta(
        credentials_missing=["CROSSTRADE_TOKEN"],
        setup_complete=False,
    ) == {"wizard_required": True, "skip_reason": None}
    assert resolve_credentials_wizard_meta(
        credentials_missing=[],
        setup_complete=False,
    ) == {"wizard_required": False, "skip_reason": "env_configured"}
    assert resolve_credentials_wizard_meta(
        credentials_missing=["CROSSTRADE_ACCOUNT"],
        setup_complete=True,
    ) == {"wizard_required": False, "skip_reason": "setup_complete"}


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
    config_manager.env_path = tmp_path / ".env"
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
            with patch.object(se, "_model_catalog_payload", return_value=[]):
                payload = se.build_onboarding_payload(serving_request=True)

    assert payload["setup_complete"] is False
    assert "credentials" in payload["required_steps"]
    assert "wizard_steps" in payload
    assert payload["backend"]["reachable"] is True
    assert "env_path" in payload["credentials"]
    assert "present" in payload["credentials"]
    assert isinstance(payload["credentials"]["present"], dict)
    assert "wizard_required" in payload["credentials"]
    assert "skip_reason" in payload["credentials"]


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
async def test_save_credentials_persists_env(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("FOO=bar\n", encoding="utf-8")
    config_manager = MagicMock()
    config_manager.parse_env_file.return_value = {"FOO": "bar"}
    config_manager.write_env_file = MagicMock()
    mock_services = (MagicMock(), config_manager, MagicMock(), MagicMock(), MagicMock(), MagicMock())

    with patch.object(se, "_services", return_value=mock_services):
        with patch.object(
            se,
            "persist_credentials_only",
            return_value=[],
        ) as persist_mock:
            with patch.object(se, "build_onboarding_payload", return_value={"setup_complete": False}):
                result = await se.save_credentials(
                    se.ConfigureCredentials(
                        LUMINA_JWT_SECRET_KEY="jwt",
                        CROSSTRADE_TOKEN="token",
                        CROSSTRADE_ACCOUNT="acct",
                    )
                )
    persist_mock.assert_called_once()
    assert result["success"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_deck_api_key_localhost(tmp_path: Path) -> None:
    config_manager = MagicMock()
    config_manager.parse_env_file.return_value = {"LUMINA_ADMIN_API_KEY": "sk_test_local"}
    mock_services = (MagicMock(), config_manager, MagicMock(), MagicMock(), MagicMock(), MagicMock())

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/setup/deck-api-key",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)

    with patch.object(se, "_services", return_value=mock_services):
        result = await se.get_deck_api_key(request)

    assert result == {"configured": True, "api_key": "sk_test_local"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_deck_credentials_prefill_localhost(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "LUMINA_JWT_SECRET_KEY=jwt\nCROSSTRADE_ACCOUNT=acct\n",
        encoding="utf-8",
    )
    config_manager = MagicMock()
    config_manager.env_path = env_path
    config_manager.parse_env_file.return_value = {
        "LUMINA_JWT_SECRET_KEY": "jwt",
        "CROSSTRADE_ACCOUNT": "acct",
        "CROSSTRADE_TOKEN": "",
    }
    mock_services = (MagicMock(), config_manager, MagicMock(), MagicMock(), MagicMock(), MagicMock())

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/setup/deck-credentials-prefill",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }
    request = Request(scope)

    with patch.object(se, "_services", return_value=mock_services):
        with patch(
            "backend.setup_endpoints.build_credentials_env_snapshot",
            return_value={
                "env_path": str(env_path.resolve()),
                "present": {
                    "LUMINA_JWT_SECRET_KEY": True,
                    "CROSSTRADE_ACCOUNT": True,
                    "CROSSTRADE_TOKEN": False,
                },
                "credentials": {
                    "LUMINA_JWT_SECRET_KEY": "jwt",
                    "CROSSTRADE_ACCOUNT": "acct",
                    "CROSSTRADE_TOKEN": "",
                },
            },
        ):
            result = await se.get_deck_credentials_prefill(request)

    assert result["env_path"] == str(env_path.resolve())
    assert result["present"]["CROSSTRADE_ACCOUNT"] is True
    assert result["credentials"]["LUMINA_JWT_SECRET_KEY"] == "jwt"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_deck_credentials_prefill_rejects_non_localhost() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/setup/deck-credentials-prefill",
        "headers": [],
        "client": ("203.0.113.1", 12345),
    }
    request = Request(scope)

    with pytest.raises(HTTPException) as exc:
        await se.get_deck_credentials_prefill(request)
    assert exc.value.status_code == 403


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_deck_api_key_rejects_non_localhost() -> None:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/setup/deck-api-key",
        "headers": [],
        "client": ("203.0.113.1", 12345),
    }
    request = Request(scope)

    with pytest.raises(HTTPException) as exc:
        await se.get_deck_api_key(request)
    assert exc.value.status_code == 403


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
