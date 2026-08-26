"""Credential-only persistence + scan helpers."""
from __future__ import annotations

import logging
import os
import secrets
from typing import Any

from lumina_launcher.core.config_manager import ConfigManager

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
    apply_fabric_token_side_effects,
)

def persist_credentials_only(
    config_manager: ConfigManager,
    credentials: dict[str, Any],
    *,
    emergency_market_data_fallback: bool | None = None,
    workspace_root: Any = None,
) -> list[str]:
    """Write credential keys to .env without completing setup.

    When ``emergency_market_data_fallback`` is provided (Vault checkbox), also
    writes ``broker.fallback_on_fabric_failure`` via the emergency opt-in SSOT.
    """
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

    # Vault emergency checkbox → machine truth (single control plane).
    flag = emergency_market_data_fallback
    if flag is None and "emergency_market_data_fallback" in credentials:
        raw = credentials.get("emergency_market_data_fallback")
        if isinstance(raw, bool):
            flag = raw
        else:
            flag = str(raw or "").strip().lower() in {"1", "true", "yes", "on"}
    if flag is not None:
        try:
            from pathlib import Path

            from lumina_core.broker.emergency_opt_in import set_market_data_fallback

            root = Path(workspace_root) if workspace_root else None
            set_market_data_fallback(
                bool(flag),
                config_manager=config_manager,
                source="vault",
                workspace_root=root,
            )
        except Exception:
            logger.warning("Failed to persist emergency_market_data_fallback", exc_info=True)

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

    # Prefill emergency checkbox from YAML SSOT (not local UI-only state).
    emergency_md = False
    try:
        from lumina_core.broker.emergency_opt_in import read_emergency_opt_in
        from pathlib import Path

        state = read_emergency_opt_in(config_path=Path(config_manager.config_path))
        emergency_md = bool(state.market_data_fallback)
    except Exception:
        broker = config_manager.load_yaml_config().get("broker")
        if isinstance(broker, dict):
            emergency_md = bool(broker.get("fallback_on_fabric_failure"))

    return {
        "env_path": str(config_manager.env_path.resolve()),
        "present": present,
        "credentials": credentials,
        "emergency_market_data_fallback": emergency_md,
        "fallback_on_fabric_failure": emergency_md,
    }
