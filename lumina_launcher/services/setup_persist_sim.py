"""SIM envelope seal + seed runtime after setup."""
from __future__ import annotations

import json
import logging
import os
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

SIM_ENVELOPE_SEALED_FILENAME = "lumina_sim_envelope_sealed.json"

from lumina_launcher.services.setup_persist_mode import resolve_mode_matrix, _ensure_mapping  # noqa: E402

def sim_envelope_sealed_path(workspace_root: Path) -> Path:
    return Path(workspace_root) / "state" / SIM_ENVELOPE_SEALED_FILENAME


def is_sim_envelope_sealed(workspace_root: Path) -> bool:
    """Whether operator sealed post-birth SIM Risk Envelope.

    Legacy installs without the flag are treated as sealed (no lock-out).
    New vault-complete path writes sealed=false explicitly.
    """
    path = sim_envelope_sealed_path(workspace_root)
    if not path.is_file():
        return True
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True
    if not isinstance(payload, dict):
        return True
    return bool(payload.get("sealed", True))


def write_sim_envelope_sealed(
    workspace_root: Path,
    *,
    sealed: bool,
    source: str = "operator",
) -> None:
    path = sim_envelope_sealed_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sealed": bool(sealed),
        "source": str(source),
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def seed_sim_runtime_and_mark_setup(
    *,
    workspace_root: Path,
    setup_service: SetupService,
    config_manager: ConfigManager,
    first_boot_manager: FirstBootManager,
    model_service: ModelService,
    snapshot: HardwareSnapshot,
    force_envelope_unsealed: bool = True,
) -> list[dict[str, Any]]:
    """After Vault is ready: force SIM runtime defaults and mark setup complete.

    Risk Envelope (capital path) is deferred to post-birth Playground seal.
    """
    steps: list[dict[str, Any]] = []
    if setup_service.is_setup_complete():
        steps.append(
            {
                "name": "setup_already_complete",
                "success": True,
                "message": "Setup already complete",
            }
        )
        return steps

    birth_mode_value, birth_backend = resolve_mode_matrix("sim")
    env_updates: dict[str, str] = {
        "TRADE_MODE": birth_mode_value,
        "LUMINA_MODE": birth_mode_value,
        "BROKER_BACKEND": birth_backend,
    }
    env_values = config_manager.parse_env_file()
    if not str(env_values.get("INSTRUMENT", "") or os.getenv("INSTRUMENT", "")).strip():
        env_updates["INSTRUMENT"] = "MES"
    config_manager.write_env_file(env_updates)
    steps.append(
        {
            "name": "env_update",
            "success": True,
            "message": "SIM runtime seeded (Birth fail-closed)",
        }
    )

    config_payload = config_manager.load_yaml_config()
    config_payload["mode"] = "sim"
    broker = _ensure_mapping(config_payload, "broker")
    broker["backend"] = birth_backend
    trading = _ensure_mapping(config_payload, "trading")
    if not str(trading.get("instrument", "")).strip():
        trading["instrument"] = "MES"
    config_manager.save_yaml_config(config_payload)
    steps.append(
        {
            "name": "runtime_mode",
            "success": True,
            "message": "config.yaml mode=sim (Risk Envelope deferred to Playground)",
        }
    )

    # Preserve any prior training targets; seed safe first-boot defaults if empty.
    first_boot_manager.save_full_settings(
        training_trades=int(
            (config_payload.get("first_boot") or {}).get("training_trades", 25000)
            if isinstance(config_payload.get("first_boot"), dict)
            else 25000
        ),
        prefer_real_data_only=True,
        max_real_days=int(
            (config_payload.get("first_boot") or {}).get("max_real_days", 365)
            if isinstance(config_payload.get("first_boot"), dict)
            else 365
        ),
        allow_minimal_synthetic_fallback=False,
        require_real_simulator_data=True,
        mark_user_configured=True,
    )
    steps.append(
        {
            "name": "first_boot_config",
            "success": True,
            "message": "First-boot defaults ready (Genesis can override)",
        }
    )

    recommended = model_service.get_recommended(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    model_result = setup_service.apply_recommended_config(hardware=snapshot, model=recommended)
    steps.append(model_result.to_dict())
    model_service.save_state(workspace_root / "state" / "model_catalog_state.json", recommended.key)

    ConfigLoader.invalidate()
    setup_service.save_status(
        {
            "steps": steps,
            "selected_mode": "sim",
            "selected_model": recommended.key,
            "hardware_tier": getattr(snapshot, "profile_tier", "unknown"),
            "source": "vault_complete_sim_seed",
        }
    )
    setup_service.mark_complete(hardware=snapshot, model=recommended)
    steps.append(
        {
            "name": "setup_complete",
            "success": True,
            "message": "Setup complete — Birth unlocked (envelope seal later)",
        }
    )

    if force_envelope_unsealed:
        # Only set unsealed when flag file does not already claim sealed=true.
        path = sim_envelope_sealed_path(workspace_root)
        if not path.is_file():
            write_sim_envelope_sealed(workspace_root, sealed=False, source="vault_complete")
        else:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(existing, dict) and existing.get("sealed") is not True:
                    write_sim_envelope_sealed(workspace_root, sealed=False, source="vault_complete")
            except (OSError, json.JSONDecodeError):
                write_sim_envelope_sealed(workspace_root, sealed=False, source="vault_complete")

    return steps


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


