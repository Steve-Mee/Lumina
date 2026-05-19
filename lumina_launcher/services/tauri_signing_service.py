"""Tauri updater signing key generation and persistence for Guided Setup."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_launcher.core.config_manager import ConfigManager

logger = get_logger(__name__)

ENV_SIGNING_KEY_PATH = "TAURI_SIGNING_PRIVATE_KEY_PATH"
DEFAULT_KEY_FILENAME = "lumina-tauri-signing.key"
_GENERATE_TIMEOUT_SEC = 120


@dataclass(slots=True)
class TauriSigningResult:
    success: bool
    message: str
    key_path: str | None = None
    public_key: str | None = None
    regenerated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "key_path": self.key_path,
            "public_key": self.public_key,
            "regenerated": self.regenerated,
        }


def default_key_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root).resolve() / "state" / DEFAULT_KEY_FILENAME


def default_public_key_path(key_path: Path | str) -> Path:
    return Path(f"{key_path}.pub")


def relative_key_path_for_env(workspace_root: Path | str, key_path: Path | str) -> str:
    root = Path(workspace_root).resolve()
    resolved = Path(key_path).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return resolved.as_posix()


def tauri_app_dir(workspace_root: Path | str) -> Path:
    return Path(workspace_root).resolve() / "tauri-app"


def tauri_conf_path(workspace_root: Path | str) -> Path:
    return tauri_app_dir(workspace_root) / "src-tauri" / "tauri.conf.json"


def is_configured(workspace_root: Path | str, env_values: dict[str, str] | None = None) -> bool:
    root = Path(workspace_root).resolve()
    env_path = str((env_values or {}).get(ENV_SIGNING_KEY_PATH, "")).strip()
    if not env_path:
        return False

    key_candidate = Path(env_path)
    if not key_candidate.is_absolute():
        key_candidate = root / key_candidate
    return key_candidate.is_file()


def read_public_key(key_path: Path | str) -> str:
    pub_path = default_public_key_path(key_path)
    if not pub_path.is_file():
        raise FileNotFoundError(f"Public key file not found: {pub_path}")
    content = pub_path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"Public key file is empty: {pub_path}")
    return content


def sync_pubkey_to_tauri_conf(workspace_root: Path | str, public_key: str) -> None:
    conf_path = tauri_conf_path(workspace_root)
    if not conf_path.is_file():
        raise FileNotFoundError(f"Tauri config not found: {conf_path}")

    payload = json.loads(conf_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid Tauri config JSON: {conf_path}")

    plugins = payload.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
        payload["plugins"] = plugins

    updater = plugins.get("updater")
    if not isinstance(updater, dict):
        updater = {}
        plugins["updater"] = updater

    updater["pubkey"] = public_key.strip()
    conf_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Updated Tauri updater pubkey in %s", conf_path)


def persist_to_env(config_manager: ConfigManager, key_path: Path | str, workspace_root: Path | str) -> str:
    relative_path = relative_key_path_for_env(workspace_root, key_path)
    config_manager.write_env_file({ENV_SIGNING_KEY_PATH: relative_path})
    return relative_path


class TauriSigningService:
    """Generate and persist Tauri minisign keys for desktop release builds."""

    def __init__(self, workspace_root: Path | str) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    @property
    def key_path(self) -> Path:
        return default_key_path(self.workspace_root)

    def is_configured(self, env_values: dict[str, str] | None = None) -> bool:
        return is_configured(self.workspace_root, env_values)

    def generate_keypair(
        self,
        *,
        config_manager: ConfigManager,
        force: bool = False,
    ) -> TauriSigningResult:
        key_path = self.key_path
        regenerated = key_path.is_file()

        if regenerated and not force:
            return TauriSigningResult(
                success=False,
                message="Signing key already exists. Use regenerate to overwrite.",
                key_path=str(key_path),
                regenerated=False,
            )

        tauri_dir = tauri_app_dir(self.workspace_root)
        if not tauri_dir.is_dir():
            return TauriSigningResult(
                success=False,
                message=f"Tauri app directory not found: {tauri_dir}",
            )

        if shutil.which("npm") is None:
            return TauriSigningResult(
                success=False,
                message="npm is not available on PATH. Install Node.js to generate Tauri signing keys.",
            )

        npm_executable = shutil.which("npm")
        assert npm_executable is not None

        key_path.parent.mkdir(parents=True, exist_ok=True)
        write_path = key_path.resolve()

        command = [
            npm_executable,
            "run",
            "tauri",
            "--",
            "signer",
            "generate",
            "-w",
            str(write_path),
            "--ci",
        ]
        if force or regenerated:
            command.append("-f")

        try:
            completed = subprocess.run(
                command,
                cwd=str(tauri_dir),
                capture_output=True,
                text=True,
                timeout=_GENERATE_TIMEOUT_SEC,
                check=False,
                shell=os.name == "nt",
            )
        except subprocess.TimeoutExpired:
            return TauriSigningResult(
                success=False,
                message="Tauri signer generate timed out.",
                regenerated=regenerated,
            )
        except OSError as exc:
            logger.exception("Failed to run tauri signer generate")
            return TauriSigningResult(
                success=False,
                message=f"Failed to run Tauri signer: {exc}",
                regenerated=regenerated,
            )

        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            return TauriSigningResult(
                success=False,
                message=f"Tauri signer generate failed: {detail or 'unknown error'}",
                regenerated=regenerated,
            )

        if not write_path.is_file():
            return TauriSigningResult(
                success=False,
                message=f"Expected private key file was not created: {write_path}",
                regenerated=regenerated,
            )

        try:
            public_key = read_public_key(write_path)
            sync_pubkey_to_tauri_conf(self.workspace_root, public_key)
            env_path = persist_to_env(config_manager, write_path, self.workspace_root)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.exception("Failed to persist Tauri signing key")
            return TauriSigningResult(
                success=False,
                message=f"Key generated but persistence failed: {exc}",
                key_path=str(write_path),
                regenerated=regenerated or force,
            )

        action = "regenerated" if (regenerated or force) else "generated"
        return TauriSigningResult(
            success=True,
            message=f"Tauri signing key {action} and saved to {env_path}",
            key_path=str(write_path),
            public_key=public_key,
            regenerated=regenerated or force,
        )
