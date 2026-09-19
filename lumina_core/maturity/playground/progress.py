"""Playground progress SSOT — operator + HUD. HUD pass_now ≡ engine AND."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def merge_playground_progress(
    workspace_root: Path | str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    current = load_playground_progress(workspace_root)
    merged = {**current, **patch}
    save_playground_progress(workspace_root, merged)
    return merged
