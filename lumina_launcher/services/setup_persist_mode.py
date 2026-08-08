"""Mode matrix + mapping helpers for setup persistence."""
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

def resolve_mode_matrix(selection: str) -> tuple[str, str]:
    normalized = str(selection or "paper").strip().lower()
    if normalized == "paper":
        return "paper", "paper"
    if normalized in {"sim", "sim_real_guard", "real"}:
        return normalized, "live"
    return "paper", "paper"


def _ensure_mapping(root: dict[str, Any], key: str) -> dict[str, Any]:
    section = root.get(key)
    if isinstance(section, dict):
        return section
    section = {}
    root[key] = section
    return section


