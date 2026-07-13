"""Atomic YAML read/write helpers for safe config hot-reload."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("lumina.config.atomic_yaml")


def resolve_config_path() -> Path:
    """Resolve config.yaml path (``LUMINA_CONFIG`` env or cwd default)."""
    return Path(os.getenv("LUMINA_CONFIG", "config.yaml"))


def _tmp_path_for(path: Path) -> Path:
    return path.with_name(f"{path.name}.tmp")


def atomic_write_yaml(path: Path | str, payload: dict[str, Any]) -> None:
    """Write YAML atomically via temp file + ``os.replace``."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
    tmp_path = _tmp_path_for(target)
    tmp_path.write_text(encoded, encoding="utf-8")
    os.replace(tmp_path, target)


def read_yaml_stable(
    path: Path | str | None = None,
    *,
    settle_ms: int = 150,
    max_attempts: int = 5,
) -> dict[str, Any]:
    """Read YAML after write settles; refuse reads while ``.tmp`` sibling exists."""
    target = Path(path) if path is not None else resolve_config_path()
    if not target.is_file():
        return {}

    tmp_path = _tmp_path_for(target)
    last_error: Exception | None = None

    for attempt in range(max(1, max_attempts)):
        if tmp_path.exists():
            time.sleep(max(0.01, settle_ms / 1000.0))
            continue
        try:
            prev_mtime = target.stat().st_mtime
            time.sleep(max(0.01, settle_ms / 1000.0))
            current_mtime = target.stat().st_mtime
            if current_mtime != prev_mtime and attempt + 1 < max_attempts:
                continue
            raw = yaml.safe_load(target.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception as exc:
            last_error = exc
            time.sleep(max(0.01, settle_ms / 1000.0))

    if last_error is not None:
        logger.warning("atomic_yaml.read_failed path=%s detail=%s", target, last_error)
    return {}
