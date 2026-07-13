"""Optional JSONL telemetry sink and run-id allocation for launcher operations."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_launcher.telemetry.events import log_event

_RUN_ID_FILE = Path("state") / "launcher_run_id.txt"
_TELEMETRY_FILE = Path("state") / "launcher_telemetry.jsonl"


def _workspace_root() -> Path:
    from lumina_launcher.core.workspace_root import resolve_birth_workspace_root

    return resolve_birth_workspace_root()


def allocate_run_id(*, workspace_root: Path | None = None) -> str:
    """Return stable run id from env or workspace state file."""
    env_id = os.getenv("LUMINA_RUN_ID", "").strip()
    if env_id:
        return env_id
    root = workspace_root or _workspace_root()
    path = root / _RUN_ID_FILE
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    run_id = uuid.uuid4().hex[:10]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run_id, encoding="utf-8")
    return run_id


def _telemetry_enabled() -> bool:
    return os.getenv("LUMINA_LAUNCHER_TELEMETRY", "").strip().lower() in {"1", "true", "yes", "on"}


def emit_launcher_event(name: str, **payload: Any) -> None:
    """Structured log + optional JSONL append when LUMINA_LAUNCHER_TELEMETRY=1."""
    run_id = payload.pop("run_id", None) or allocate_run_id()
    log_event(name, run_id=run_id, **payload)
    if not _telemetry_enabled():
        return
    root = _workspace_root()
    path = root / _TELEMETRY_FILE
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": name,
        "run_id": run_id,
        **payload,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
