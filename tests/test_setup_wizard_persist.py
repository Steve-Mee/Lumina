from __future__ import annotations

import json
from pathlib import Path

import yaml

from lumina_core.engine.hardware_inspector import HardwareSnapshot
from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.model_service import ModelService
from lumina_launcher.ui.setup_wizard import persist_setup_configuration, resolve_mode_matrix


def test_resolve_mode_matrix() -> None:
    assert resolve_mode_matrix("paper") == ("paper", "paper")
    assert resolve_mode_matrix("sim") == ("sim", "live")
    assert resolve_mode_matrix("real") == ("real", "live")
    assert resolve_mode_matrix("sim_real_guard") == ("sim_real_guard", "live")
    assert resolve_mode_matrix("unknown") == ("paper", "paper")


def test_persist_setup_configuration_writes_env_yaml_and_state(tmp_path: Path) -> None:
    workspace_root = tmp_path
    config_path = workspace_root / "config.yaml"
    config_path.write_text(yaml.safe_dump({"mode": "paper", "broker": {"backend": "paper"}}), encoding="utf-8")

    config_manager = ConfigManager(workspace_root / ".env", config_path)
    first_boot_manager = FirstBootManager(workspace_root)
    setup_service = SetupService(
        workspace_root=workspace_root,
        config_path=config_path,
        env_path=workspace_root / ".env",
    )
    catalog_path = Path(__file__).resolve().parents[1] / "lumina_model_catalog.json"
    model_service = ModelService(catalog_path)

    snapshot = HardwareSnapshot(
        os_name="Linux",
        os_version="test",
        cpu_name="cpu",
        cpu_cores_physical=8,
        cpu_cores_logical=16,
        ram_gb=64.0,
        gpu_name="RTX 4090",
        gpu_vram_gb=24.0,
        compute_capability=8.9,
        ollama_installed=True,
        ollama_running=True,
        nvidia_smi_available=True,
        vllm_supported=True,
        profile_tier="beast",
        recommended_model_key="qwen3.5-35b",
        recommended_provider="vllm",
        recommended_context_length=16384,
        notes=[],
    )

    steps = persist_setup_configuration(
        workspace_root=workspace_root,
        setup_service=setup_service,
        config_manager=config_manager,
        first_boot_manager=first_boot_manager,
        model_service=model_service,
        snapshot=snapshot,
        selected_model_key="qwen3.5-9b",
        mode_selection="sim",
        credentials={
            "CROSSTRADE_TOKEN": "test-token",
            "CROSSTRADE_ACCOUNT": "DEMO123",
            "XAI_API_KEY": "xai-test",
            "TELEGRAM_BOT_TOKEN": "tg-bot",
            "TELEGRAM_CHAT_ID": "1234",
            "LUMINA_JWT_SECRET_KEY": "jwt-secret-test",
            "LUMINA_ADMIN_API_KEY": "sk_test_admin_key",
        },
        training={
            "training_trades": 15000,
            "prefer_real_data_only": True,
            "max_real_days": 120,
            "allow_minimal_synthetic_fallback": False,
            "require_real_simulator_data": True,
        },
    )

    env_text = (workspace_root / ".env").read_text(encoding="utf-8")
    assert "TRADE_MODE=sim" in env_text
    assert "BROKER_BACKEND=live" in env_text
    assert "CROSSTRADE_TOKEN=test-token" in env_text
    assert "LUMINA_ADMIN_API_KEY=sk_test_admin_key" in env_text

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert payload["mode"] == "sim"
    assert payload["broker"]["backend"] == "live"
    assert payload["first_boot"]["training_trades"] == 15000
    assert payload["first_boot"]["prefer_real_data_only"] is True
    assert payload["evolution"]["neuroevolution"]["require_real_simulator_data"] is True
    assert payload["models"]["reasoning"] == "qwen3.5:9b"

    status_path = workspace_root / "state" / "lumina_setup_status.json"
    complete_path = workspace_root / "state" / "lumina_setup_complete.json"
    assert status_path.exists()
    assert complete_path.exists()
    status_payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert status_payload["selected_mode"] == "sim"
    assert any(step.get("name") == "config_update" and step.get("success") for step in steps)


def test_persist_setup_configuration_auto_generates_admin_api_key_when_missing(tmp_path: Path) -> None:
    workspace_root = tmp_path
    config_path = workspace_root / "config.yaml"
    config_path.write_text(yaml.safe_dump({"mode": "paper", "broker": {"backend": "paper"}}), encoding="utf-8")

    config_manager = ConfigManager(workspace_root / ".env", config_path)
    first_boot_manager = FirstBootManager(workspace_root)
    setup_service = SetupService(
        workspace_root=workspace_root,
        config_path=config_path,
        env_path=workspace_root / ".env",
    )
    catalog_path = Path(__file__).resolve().parents[1] / "lumina_model_catalog.json"
    model_service = ModelService(catalog_path)

    snapshot = HardwareSnapshot(
        os_name="Linux",
        os_version="test",
        cpu_name="cpu",
        cpu_cores_physical=8,
        cpu_cores_logical=16,
        ram_gb=64.0,
        gpu_name="RTX 4090",
        gpu_vram_gb=24.0,
        compute_capability=8.9,
        ollama_installed=True,
        ollama_running=True,
        nvidia_smi_available=True,
        vllm_supported=True,
        profile_tier="beast",
        recommended_model_key="qwen3.5-35b",
        recommended_provider="vllm",
        recommended_context_length=16384,
        notes=[],
    )

    steps = persist_setup_configuration(
        workspace_root=workspace_root,
        setup_service=setup_service,
        config_manager=config_manager,
        first_boot_manager=first_boot_manager,
        model_service=model_service,
        snapshot=snapshot,
        selected_model_key="qwen3.5-9b",
        mode_selection="sim",
        credentials={
            "CROSSTRADE_TOKEN": "test-token",
            "CROSSTRADE_ACCOUNT": "DEMO123",
            "XAI_API_KEY": "xai-test",
            "TELEGRAM_BOT_TOKEN": "tg-bot",
            "TELEGRAM_CHAT_ID": "1234",
            "LUMINA_JWT_SECRET_KEY": "jwt-secret-test",
            "LUMINA_ADMIN_API_KEY": "",
        },
        training={
            "training_trades": 15000,
            "prefer_real_data_only": True,
            "max_real_days": 120,
            "allow_minimal_synthetic_fallback": False,
            "require_real_simulator_data": True,
        },
    )

    env_text = (workspace_root / ".env").read_text(encoding="utf-8")
    admin_line = next((line for line in env_text.splitlines() if line.startswith("LUMINA_ADMIN_API_KEY=")), "")
    assert admin_line.startswith("LUMINA_ADMIN_API_KEY=sk_")
    assert len(admin_line.split("=", 1)[1].strip()) > 20
    assert any(step.get("name") == "admin_api_key" and step.get("success") for step in steps)
