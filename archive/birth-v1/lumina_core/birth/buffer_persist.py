"""Persist trajectory buffer for checkpoint v3 resume."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def buffer_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / "state" / "lumina_birth_buffer.jsonl"


def save_buffer(workspace_root: Path | str, trajectories: list[dict[str, Any]]) -> str:
    path = buffer_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item, ensure_ascii=True) for item in trajectories[-500_000:]]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return str(path)


def load_buffer(workspace_root: Path | str) -> list[dict[str, Any]]:
    path = buffer_path(workspace_root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append(item)
    return out


def clear_buffer(workspace_root: Path | str) -> None:
    path = buffer_path(workspace_root)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
