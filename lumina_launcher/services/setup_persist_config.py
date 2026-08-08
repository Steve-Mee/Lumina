"""Full setup configuration persistence (wizard + onboarding)."""
from __future__ import annotations

import json
import logging
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.engine.hardware_inspector import HardwareSnapshot
from lumina_core.engine.setup_service import SetupService
from lumina_launcher.core.config_manager import ConfigManager
from lumina_launcher.core.first_boot import FirstBootManager
from lumina_launcher.services.model_service import ModelService

logger = logging.getLogger(__name__)

def persist_setup_configuration(
    *,
    workspace_root: Path,
    setup_service: SetupService,
    config_manager: ConfigManager,
    first_boot_manager: FirstBootManager,
    model_service: ModelService,
    snapshot: HardwareSnapshot,
    selected_model_key: str,
    mode_selection: str,
    credentials: dict[str, str],
    training: dict[str, Any],
    admin_password: str = "",
) -> list[dict[str, Any]]:
    from lumina_launcher.core.admin_auth import AdminAuth

    mode_value, broker_backend = resolve_mode_matrix(mode_selection)
    birth_mode_value, birth_backend = resolve_mode_matrix("sim")
    admin_api_key = str(credentials.get("LUMINA_ADMIN_API_KEY", "")).strip() or f"sk_{secrets.token_hex(32)}"
    env_updates = {
        "TRADE_MODE": birth_mode_value,
        "LUMINA_MODE": birth_mode_value,
        "BROKER_BACKEND": birth_backend,
        "LUMINA_ADMIN_API_KEY": admin_api_key,
    }
    for key in (
        "CROSSTRADE_TOKEN",
        "CROSSTRADE_ACCOUNT",
        "XAI_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "LUMINA_JWT_SECRET_KEY",
        "LUMINA_FABRIC_TOKEN",
        "TAURI_SIGNING_PRIVATE_KEY_PATH",
    ):
        value = str(credentials.get(key, "")).strip()
        if value:
            env_updates[key] = value

    steps: list[dict[str, Any]] = []
    config_manager.write_env_file(env_updates)
    fabric_token = str(credentials.get("LUMINA_FABRIC_TOKEN", "")).strip()
    if fabric_token:
        apply_fabric_token_side_effects(fabric_token)
    steps.append({"name": "env_update", "success": True, "message": "Environment values written"})
    if not str(credentials.get("LUMINA_ADMIN_API_KEY", "")).strip():
        steps.append(
            {
                "name": "admin_api_key",
                "success": True,
                "message": "Admin API key auto-generated and stored in .env",
            }
        )

    config_payload = config_manager.load_yaml_config()
    config_payload["mode"] = mode_value
    broker = config_payload.get("broker")
    if not isinstance(broker, dict):
        broker = {}
    broker["backend"] = broker_backend
    config_payload["broker"] = broker
    config_manager.save_yaml_config(config_payload)
    steps.append(
        {
            "name": "runtime_mode",
            "success": True,
            "message": f"Mode set to {mode_value}/{broker_backend} (first-boot runtime forced to sim/{birth_backend})",
        }
    )

    first_boot_manager.save_full_settings(
        training_trades=int(training["training_trades"]),
        prefer_real_data_only=bool(training["prefer_real_data_only"]),
        max_real_days=int(training["max_real_days"]),
        allow_minimal_synthetic_fallback=bool(training["allow_minimal_synthetic_fallback"]),
        require_real_simulator_data=bool(
            training.get("require_real_simulator_data", training["prefer_real_data_only"])
        ),
        mark_user_configured=True,
    )
    first_boot_manager.save_neuro_require_real_simulator_data(
        bool(training.get("require_real_simulator_data", training["prefer_real_data_only"]))
    )
    steps.append({"name": "first_boot_config", "success": True, "message": "First-boot training settings saved"})

    if admin_password:
        if len(admin_password) >= 12:
            AdminAuth(workspace_root / "state" / "launcher_admin_password.json").set_password(admin_password)
            steps.append({"name": "admin_password", "success": True, "message": "Admin password configured"})
        else:
            steps.append(
                {
                    "name": "admin_password",
                    "success": False,
                    "message": "Admin password skipped (must be at least 12 characters).",
                }
            )

    model = model_service.get_model(selected_model_key) or model_service.get_catalog().models()[0]
    model_result = setup_service.apply_recommended_config(hardware=snapshot, model=model)
    steps.append(model_result.to_dict())
    model_service.save_state(workspace_root / "state" / "model_catalog_state.json", model.key)

    ConfigLoader.invalidate()
    setup_service.save_status(
        {
            "steps": steps,
            "selected_mode": mode_value,
            "selected_model": model.key,
            "hardware_tier": getattr(snapshot, "profile_tier", "unknown"),
        }
    )

    required = {"env_update", "runtime_mode", "first_boot_config", "config_update"}
    ok_names = {step.get("name") for step in steps if step.get("success")}
    if required.issubset(ok_names):
        setup_service.mark_complete(hardware=snapshot, model=model)
    return steps


