"""
LUMINA Core - Config Manager
Handles .env and config.yaml loading/saving.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lumina_core.config.atomic_yaml import atomic_write_yaml


class ConfigManager:
    def __init__(self, env_path: Path, config_path: Path):
        self.env_path = env_path
        self.config_path = config_path

    @staticmethod
    def _normalize_env_key(raw_key: str) -> str:
        return raw_key.strip().lstrip("\ufeff")

    @staticmethod
    def _normalize_env_value(raw_value: str) -> str:
        return raw_value.split("#", 1)[0].strip()

    def parse_env_file(self) -> dict[str, str]:
        if not self.env_path.exists():
            return {}
        values: dict[str, str] = {}
        text = self.env_path.read_text(encoding="utf-8-sig")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            normalized_key = self._normalize_env_key(key)
            if not normalized_key:
                continue
            values[normalized_key] = self._normalize_env_value(value)
        return values

    def write_env_file(self, updates: dict[str, str]) -> None:
        merged = self.parse_env_file()
        merged.update({k: str(v) for k, v in updates.items()})
        content = "\n".join(f"{k}={v}" for k, v in sorted(merged.items())) + "\n"
        self.env_path.write_text(content, encoding="utf-8")

    def load_yaml_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        payload = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    def save_yaml_config(self, data: dict[str, Any]) -> None:
        atomic_write_yaml(self.config_path, data)
