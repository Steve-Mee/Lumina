"""Shared setup persistence helpers (Streamlit wizard + Tauri onboarding)."""

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

# Operator defaults for %APPDATA%/LUMINA/fabric.json (never store token value here).
DEFAULT_FABRIC_JSON: dict[str, Any] = {
    "BindHost": "127.0.0.1",
    "BindPort": 50051,
    "AuthTokenEnv": "LUMINA_FABRIC_TOKEN",
    "AccountName": "Sim101",
    "GatewayMode": "sim",
    "HeartbeatTimeoutMs": 5000,
    "FlattenGraceMs": 15000,
    "FlattenOnTimeout": True,
    "BindLocalhostOnly": True,
    "MaxPositionSize": 2,
    "MaxOrdersPerMinute": 30,
    "DailyLossLimit": 0,
}


def resolve_mode_matrix(selection: str) -> tuple[str, str]:
    normalized = str(selection or "paper").strip().lower()
    if normalized == "paper":
        return "paper", "paper"
    if normalized in {"sim", "sim_real_guard", "real"}:
        return normalized, "live"
    return "paper", "paper"


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


def _ensure_mapping(root: dict[str, Any], key: str) -> dict[str, Any]:
    section = root.get(key)
    if isinstance(section, dict):
        return section
    section = {}
    root[key] = section
    return section


def persist_tauri_quick_config(
    *,
    workspace_root: Path,
    setup_service: SetupService,
    config_manager: ConfigManager,
    first_boot_manager: FirstBootManager,
    model_service: ModelService,
    snapshot: HardwareSnapshot,
    mode_selection: str,
    credentials: dict[str, str],
    risk: dict[str, Any],
    evolution: dict[str, Any],
    training: dict[str, Any],
    selected_model_key: str | None = None,
) -> list[dict[str, Any]]:
    """Streamlined configure path for the Tauri onboarding wizard."""
    mode_value, broker_backend = resolve_mode_matrix(mode_selection)
    birth_mode_value, birth_backend = resolve_mode_matrix("sim")
    admin_api_key = str(credentials.get("LUMINA_ADMIN_API_KEY", "")).strip() or f"sk_{secrets.token_hex(32)}"

    env_updates: dict[str, str] = {
        "TRADE_MODE": birth_mode_value,
        "LUMINA_MODE": birth_mode_value,
        "BROKER_BACKEND": birth_backend,
        "LUMINA_ADMIN_API_KEY": admin_api_key,
    }
    for key in (
        "CROSSTRADE_TOKEN",
        "CROSSTRADE_ACCOUNT",
        "LUMINA_JWT_SECRET_KEY",
    ):
        value = str(credentials.get(key, "")).strip()
        if value:
            env_updates[key] = value

    steps: list[dict[str, Any]] = []
    config_manager.write_env_file(env_updates)
    steps.append({"name": "env_update", "success": True, "message": "Environment values written"})

    config_payload = config_manager.load_yaml_config()
    config_payload["mode"] = mode_value
    broker = _ensure_mapping(config_payload, "broker")
    broker["backend"] = broker_backend

    mode_section = _ensure_mapping(config_payload, mode_value if mode_value in {"sim", "real"} else "sim")
    if "kelly_fraction" in risk:
        mode_section["kelly_fraction"] = float(risk["kelly_fraction"])
    if "daily_loss_cap" in risk and risk["daily_loss_cap"] is not None:
        mode_section["daily_loss_cap"] = float(risk["daily_loss_cap"])
    if "max_total_open_risk" in risk:
        mode_section["max_total_open_risk"] = float(risk["max_total_open_risk"])
    if "aggressive_evolution" in evolution:
        mode_section["aggressive_evolution"] = bool(evolution["aggressive_evolution"])
    if "approval_required" in evolution:
        mode_section["approval_required"] = bool(evolution["approval_required"])
    if "max_mutation_depth" in evolution:
        mode_section["max_mutation_depth"] = str(evolution["max_mutation_depth"]).strip().lower()

    risk_controller = _ensure_mapping(config_payload, "risk_controller")
    if "real_capital_safety_threshold_usd" in risk:
        risk_controller["real_capital_safety_threshold_usd"] = float(risk["real_capital_safety_threshold_usd"])
    if "max_total_open_risk" in risk:
        risk_controller["max_total_open_risk"] = float(risk["max_total_open_risk"])

    evolution_section = _ensure_mapping(config_payload, "evolution")
    if "approval_required" in evolution:
        evolution_section["approval_required"] = bool(evolution["approval_required"])

    config_manager.save_yaml_config(config_payload)
    steps.append({"name": "runtime_mode", "success": True, "message": f"Mode and risk config saved ({mode_value})"})

    gate_raw = training.get("stage1_winrate_pass_threshold")
    gate_threshold = float(gate_raw) if gate_raw is not None else None
    first_boot_manager.save_full_settings(
        training_trades=int(training["training_trades"]),
        prefer_real_data_only=bool(training.get("prefer_real_data_only", True)),
        max_real_days=int(training.get("max_real_days", 56)),
        allow_minimal_synthetic_fallback=bool(training.get("allow_minimal_synthetic_fallback", False)),
        require_real_simulator_data=bool(training.get("require_real_simulator_data", True)),
        stage1_winrate_pass_threshold=gate_threshold,
        mark_user_configured=True,
    )
    steps.append({"name": "first_boot_config", "success": True, "message": "Birth training settings saved"})
    try:
        from lumina_core.maturity.milestone_hooks import try_record_milestone

        try_record_milestone(workspace_root, "genesis_contract_signed")
    except Exception:
        pass

    recommended = model_service.get_recommended(
        ram_gb=snapshot.ram_gb,
        gpu_vram_gb=snapshot.gpu_vram_gb,
        vllm_supported=snapshot.vllm_supported,
    )
    model_key = selected_model_key or recommended.key
    model = model_service.get_model(model_key) or recommended
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
            "source": "tauri_onboarding",
        }
    )

    required = {"env_update", "runtime_mode", "first_boot_config", "config_update"}
    ok_names = {step.get("name") for step in steps if step.get("success")}
    if required.issubset(ok_names):
        setup_service.mark_complete(hardware=snapshot, model=model)
        # Defer Playground Risk Envelope seal unless operator already sealed.
        seal_path = sim_envelope_sealed_path(workspace_root)
        if not seal_path.is_file() or not is_sim_envelope_sealed(workspace_root):
            write_sim_envelope_sealed(
                workspace_root, sealed=False, source="tauri_quick_config"
            )
    return steps


def fabric_json_path() -> Path:
    """Return %APPDATA%/LUMINA/fabric.json (Windows) or ~/.config/LUMINA/fabric.json."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "LUMINA" / "fabric.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "LUMINA" / "fabric.json"
    return Path.home() / ".config" / "LUMINA" / "fabric.json"


def write_fabric_json_defaults(*, path: Path | None = None) -> Path:
    """Write operator fabric.json defaults (no auth token value). Creates parent dirs."""
    target = path or fabric_json_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(DEFAULT_FABRIC_JSON)
    # Preserve operator GatewayMode / ports if file already exists.
    if target.is_file():
        try:
            existing = json.loads(target.read_text(encoding="utf-8-sig"))
            if isinstance(existing, dict):
                for key in ("GatewayMode", "BindHost", "BindPort", "AccountName", "AuthTokenEnv"):
                    if key in existing and existing[key] is not None:
                        payload[key] = existing[key]
                # Never keep plaintext AuthToken in the onboarding-written file.
                payload.pop("AuthToken", None)
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not merge existing fabric.json; rewriting defaults", exc_info=True)
    # Write UTF-8 without BOM so C# and Python parsers agree.
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def set_user_environment_variable(name: str, value: str) -> bool:
    """Best-effort set User-level env var so NT8 can read it after process restart.

    On Windows uses .NET Environment.SetEnvironmentVariable User scope via PowerShell.
    Returns True when the write was attempted successfully.
    """
    name = str(name or "").strip()
    value = str(value or "").strip()
    if not name or not value:
        return False
    # Current process (so Brain/backend in this session can use it immediately).
    os.environ[name] = value
    if sys.platform != "win32":
        return True
    try:
        # User scope so new processes (NinjaTrader) inherit the secret.
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"[Environment]::SetEnvironmentVariable('{name}', $env:__LUMINA_SET_VAL, 'User')",
            ],
            check=False,
            capture_output=True,
            text=True,
            env={**os.environ, "__LUMINA_SET_VAL": value},
            timeout=15,
        )
        if completed.returncode != 0:
            logger.warning(
                "User env set failed for %s: rc=%s stderr=%s",
                name,
                completed.returncode,
                (completed.stderr or "").strip()[:400],
            )
            return False
        return True
    except Exception:
        logger.warning("User env set failed for %s", name, exc_info=True)
        return False


def apply_fabric_token_side_effects(token: str) -> dict[str, Any]:
    """Write fabric.json defaults and set User env for LUMINA_FABRIC_TOKEN."""
    token = str(token or "").strip()
    result: dict[str, Any] = {"fabric_json": None, "user_env": False}
    if not token:
        return result
    try:
        path = write_fabric_json_defaults()
        result["fabric_json"] = str(path)
    except OSError:
        logger.exception("Failed to write fabric.json")
    result["user_env"] = set_user_environment_variable("LUMINA_FABRIC_TOKEN", token)
    return result


def generate_fabric_token() -> str:
    """Cryptographically strong url-safe token for LUMINA_FABRIC_TOKEN."""
    return secrets.token_urlsafe(32)


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
            (config_payload.get("first_boot") or {}).get("max_real_days", 56)
            if isinstance(config_payload.get("first_boot"), dict)
            else 56
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
