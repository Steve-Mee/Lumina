"""Append-only SHADOW JSONL. Fail-closed on write errors (logged, never places)."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.research_bridge.jsonl")

_DEFAULT_NAME = "research_shadow.jsonl"


def default_shadow_jsonl_path() -> Path:
    root = Path(os.environ.get("LUMINA_STATE_DIR", "state"))
    return root / _DEFAULT_NAME


def append_shadow_record(path: Path, record: Mapping[str, object]) -> None:
    """Append one JSON object. Creates parent directories. Never raises to a broker."""
    payload = dict(record)
    if "ts_utc" not in payload:
        payload["ts_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        line = json.dumps(payload, sort_keys=True, default=str, allow_nan=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, TypeError, ValueError) as exc:
        logger.error(
            "research_shadow.jsonl_append_failed",
            extra={
                "event_data": {
                    "event": "research_shadow.jsonl_append_failed",
                    "path": str(path),
                    "error": str(exc),
                }
            },
        )
        return
    logger.info(
        "research_shadow.jsonl_append",
        extra={"event_data": {"event": "research_shadow.jsonl_append", "path": str(path)}},
    )
