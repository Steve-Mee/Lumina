"""Mode matrix + mapping helpers for setup persistence."""
from __future__ import annotations

import logging
from typing import Any


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


