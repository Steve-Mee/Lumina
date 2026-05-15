"""
LUMINA Core - First Boot Manager
Handles first-boot training settings, progress, pause/resume, and policy artifacts.
Extracted from the original God file.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from lumina_core.first_boot_ui import (
    FIRST_BOOT_DEFAULT_MAX_REAL_DAYS,
    FIRST_BOOT_DEFAULT_TRADES,
    normalize_first_boot_training_trades,
)

logger = logging.getLogger(__name__)


class FirstBootManager:
    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.config_path = workspace_root / "config.yaml"
        self.progress_path = workspace_root / "state" / "first_boot_progress.json"
        self.checkpoint_path = workspace_root / "state" / "first_boot_checkpoint.json"
        self.pause_flag_path = workspace_root / "state" / "first_boot_pause_requested"
        self.flag_path = workspace_root / "state" / "first_boot_completed.flag"
        self.policy_path = workspace_root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"

    def _load_yaml_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    def _save_yaml_config(self, data: dict[str, Any]) -> None:
        self.config_path.write_text(
            yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def read_settings(self) -> dict[str, Any]:
        cfg = self._load_yaml_config()
        section = cfg.get("first_boot", {}) if isinstance(cfg.get("first_boot"), dict) else {}
        return {
            "training_trades": normalize_first_boot_training_trades(
                section.get("training_trades", FIRST_BOOT_DEFAULT_TRADES)
            ),
            "prefer_real_data_only": bool(section.get("prefer_real_data_only", True)),
            "max_real_days": max(
                30, int(section.get("max_real_days", FIRST_BOOT_DEFAULT_MAX_REAL_DAYS) or FIRST_BOOT_DEFAULT_MAX_REAL_DAYS)
            ),
            "allow_minimal_synthetic_fallback": bool(section.get("allow_minimal_synthetic_fallback", False)),
        }

    def save_settings(self, training_trades: int) -> None:
        cfg = self._load_yaml_config()
        first_boot = cfg.setdefault("first_boot", {})
        first_boot["training_trades"] = normalize_first_boot_training_trades(training_trades)
        first_boot.setdefault("prefer_real_data_only", True)
        first_boot["max_real_days"] = max(30, int(first_boot.get("max_real_days", FIRST_BOOT_DEFAULT_MAX_REAL_DAYS) or FIRST_BOOT_DEFAULT_MAX_REAL_DAYS))
        first_boot["allow_minimal_synthetic_fallback"] = bool(first_boot.get("allow_minimal_synthetic_fallback", False))
        first_boot["force_training"] = True
        self._save_yaml_config(cfg)

    def read_progress(self) -> dict[str, Any]:
        if not self.progress_path.exists():
            return {}
        try:
            return json.loads(self.progress_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def read_checkpoint(self) -> dict[str, Any]:
        if not self.checkpoint_path.exists():
            return {}
        try:
            return json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def request_pause(self) -> None:
        self.pause_flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.pause_flag_path.write_text(datetime.now().isoformat(), encoding="utf-8")

    def clear_pause_request(self) -> None:
        try:
            if self.pause_flag_path.exists():
                self.pause_flag_path.unlink()
        except Exception:
            pass

    def artifacts_missing(self) -> bool:
        return (not self.flag_path.exists()) or (not self.policy_path.exists())

    def get_stage_progress(self, stage: str) -> float:
        stage_map = {
            "detected": 0.2,
            "loading_data": 0.45,
            "training_running": 0.75,
            "paused": 0.75,
            "completed": 1.0,
            "failed": 1.0,
        }
        return float(stage_map.get(str(stage).strip().lower(), 0.1))

    def is_completed(self) -> bool:
        return self.flag_path.exists() and self.policy_path.exists()
