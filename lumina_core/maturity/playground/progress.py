"""Playground progress SSOT — operator + HUD. HUD pass_now ≡ engine AND."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA = "playground_progress_v1"
PROGRESS_REL = Path("state") / "lumina_playground_progress.json"


def progress_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / PROGRESS_REL


def load_playground_progress(workspace_root: Path | str) -> dict[str, Any]:
    path = progress_path(workspace_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_playground_progress(workspace_root: Path | str, payload: dict[str, Any]) -> None:
    from lumina_core.io.atomic_fs import atomic_write_text

    path = progress_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data["schema"] = SCHEMA
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    atomic_write_text(path, json.dumps(data, ensure_ascii=True, indent=2) + "\n")


def read_progress_for_merge(path: Path) -> dict[str, Any] | None:
    """Current progress, or None when the file exists and every read failed.

    None tells the caller not to replace the file. An empty dict is only for a missing file.
    """
    if not path.is_file():
        return {}
    for _ in range(5):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            time.sleep(0.02)
            continue
        if isinstance(raw, dict):
            return raw
        time.sleep(0.02)
    return None


def merge_playground_progress(
    workspace_root: Path | str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    path = progress_path(workspace_root)
    current = read_progress_for_merge(path)
    if current is None:
        logger.warning("playground.progress.read_failed path=%s", path)
        return {}
    merged = {**current, **patch}
    save_playground_progress(workspace_root, merged)
    return merged
