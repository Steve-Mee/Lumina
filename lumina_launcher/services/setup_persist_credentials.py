"""Credential-only persistence + scan helpers."""
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

CREDENTIAL_ENV_KEYS: tuple[str, ...] = (
    "LUMINA_JWT_SECRET_KEY",
    "CROSSTRADE_TOKEN",
    "CROSSTRADE_ACCOUNT",
    "LUMINA_ADMIN_API_KEY",
    "LUMINA_FABRIC_TOKEN",
    "XAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


from lumina_launcher.services.setup_persist_fabric import (  # noqa: E402
    DEFAULT_FABRIC_JSON,
    apply_fabric_token_side_effects,
    fabric_json_path,
    generate_fabric_token,
    set_user_environment_variable,
    write_fabric_json_defaults,
)

def persist_credentials_only(
    config_manager: ConfigManager,
    credentials: dict[str, str],
) -> list[str]:
    """Write credential keys to .env without completing setup."""
    admin_api_key = str(credentials.get("LUMINA_ADMIN_API_KEY", "")).strip() or f"sk_{secrets.token_hex(32)}"
    env_updates: dict[str, str] = {"LUMINA_ADMIN_API_KEY": admin_api_key}
    for key in (
        "CROSSTRADE_TOKEN",
        "CROSSTRADE_ACCOUNT",
        "LUMINA_JWT_SECRET_KEY",
        "LUMINA_FABRIC_TOKEN",
        "XAI_API_KEY",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TAURI_SIGNING_PRIVATE_KEY_PATH",
    ):
        value = str(credentials.get(key, "")).strip()
        if value:
            env_updates[key] = value
    config_manager.write_env_file(env_updates)
    fabric_token = str(credentials.get("LUMINA_FABRIC_TOKEN", "")).strip()
    if fabric_token:
        apply_fabric_token_side_effects(fabric_token)
    return scan_missing_credentials(config_manager)


SIM_ENVELOPE_SEALED_FILENAME = "lumina_sim_envelope_sealed.json"


def scan_missing_credentials(config_manager: ConfigManager) -> list[str]:
    """Required secrets for Fabric-first setup.

    CrossTrade is optional emergency fallback — never hard-required.
    LUMINA_FABRIC_TOKEN is required for Genesis / operator seal.
    """
    env_values = config_manager.parse_env_file()
    required = ("LUMINA_JWT_SECRET_KEY", "LUMINA_FABRIC_TOKEN")
    missing: list[str] = []
    for key in required:
        if not str(env_values.get(key, "")).strip():
            # Also accept process env (User scope / session)
            if not str(os.getenv(key, "") or "").strip():
                missing.append(key)
    return missing


def build_credentials_env_snapshot(config_manager: ConfigManager) -> dict[str, Any]:
    """Read .env credential keys for deck prefill and onboarding status (no masking)."""
    env_values = config_manager.parse_env_file()
    present: dict[str, bool] = {}
    credentials: dict[str, str] = {}
    for key in CREDENTIAL_ENV_KEYS:
        value = str(env_values.get(key, "")).strip()
        present[key] = bool(value)
        credentials[key] = value
    return {
        "env_path": str(config_manager.env_path.resolve()),
        "present": present,
        "credentials": credentials,
    }
