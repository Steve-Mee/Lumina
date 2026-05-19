"""Launcher setup preferences from config.yaml `setup:` section."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from lumina_launcher.core.workspace_root import resolve_birth_workspace_root

logger = logging.getLogger(__name__)

SetupMode = Literal["smart", "classic", "manual"]
VALID_SETUP_MODES = frozenset({"smart", "classic", "manual"})


@dataclass(frozen=True, slots=True)
class SetupConfig:
    mode: SetupMode = "smart"
    auto_install_ollama: bool = True
    auto_download_model: bool = True
    allow_force_tier: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> SetupConfig:
        if not raw:
            return cls()
        mode_raw = str(raw.get("mode", "smart") or "smart").strip().lower()
        if mode_raw not in VALID_SETUP_MODES:
            logger.warning("setup.config.invalid_mode value=%s fallback=smart", mode_raw)
            mode_raw = "smart"
        return cls(
            mode=mode_raw,  # type: ignore[arg-type]
            auto_install_ollama=bool(raw.get("auto_install_ollama", True)),
            auto_download_model=bool(raw.get("auto_download_model", True)),
            allow_force_tier=bool(raw.get("allow_force_tier", False)),
        )

    @classmethod
    def from_workspace(cls, workspace_root: Path | str | None = None) -> SetupConfig:
        root = resolve_birth_workspace_root(workspace_root)
        config_path = root / "config.yaml"
        if not config_path.exists():
            return cls()
        try:
            payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            logger.warning("setup.config.read_failed path=%s detail=%s", config_path, exc)
            return cls()
        setup = payload.get("setup")
        if not isinstance(setup, dict):
            return cls()
        return cls.from_dict(setup)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "auto_install_ollama": self.auto_install_ollama,
            "auto_download_model": self.auto_download_model,
            "allow_force_tier": self.allow_force_tier,
        }

    def default_install_ollama(self) -> bool:
        if self.mode == "manual":
            return False
        return self.auto_install_ollama

    def default_download_model(self) -> bool:
        if self.mode == "manual":
            return False
        return self.auto_download_model

    def default_force_high_tier(self) -> bool:
        if not self.allow_force_tier:
            return False
        return False

    def to_smart_setup_options(self) -> Any:
        from lumina_launcher.services.smart_setup_service import SmartSetupOptions

        return SmartSetupOptions(
            install_ollama=self.default_install_ollama(),
            download_recommended_model=self.default_download_model(),
            force_high_tier=self.default_force_high_tier(),
        )

    def skips_smart_setup_wizard(self) -> bool:
        return self.mode == "classic"
