"""Fabric JSON defaults + token environment side-effects."""
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


