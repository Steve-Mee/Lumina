"""M1: append-only architecture evolution journal (never auto-apply)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_REL = Path("logs") / "architecture_evolution.jsonl"


def journal_path(workspace_root: Path | str | None = None) -> Path:
    if workspace_root is None:
        return DEFAULT_REL
    return Path(workspace_root) / DEFAULT_REL


def append_architecture_event(
    event: dict[str, Any],
    *,
    workspace_root: Path | str | None = None,
    path: Path | None = None,
) -> Path:
    """Append one JSON line. Creates parent dirs. Fail-soft on write errors → raises."""
    p = path or journal_path(workspace_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(event)
    payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
    payload.setdefault("schema", "architecture_evolution_v1")
    # Never claim auto-apply
    if payload.get("action") == "apply":
        payload["action"] = "apply_blocked"
        payload["note"] = "architecture_meta never auto-applies; human marker required"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")
    return p


def tail_architecture_events(
    *,
    workspace_root: Path | str | None = None,
    path: Path | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    p = path or journal_path(workspace_root)
    if not p.is_file():
        return []
    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, int(limit)) :]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
