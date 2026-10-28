"""Append-only JSONL audit log. Writing this log cannot be skipped."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


class AuditError(RuntimeError):
    """Audit persistence failed. Fail closed: the caller must not continue silently."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_audit_path() -> Path:
    root = os.environ.get("LUMINA_STATE_DIR", "state")
    return Path(root) / "research_validation_audit.jsonl"


@dataclass(frozen=True, slots=True)
class AuditRecord:
    timestamp: str
    agent_id: str
    event: str
    metrics: Mapping[str, object]


class AuditLog:
    """Append-only JSONL. Subclassing is forbidden so writers cannot no-op append."""

    def __init_subclass__(cls) -> None:
        raise TypeError("AuditLog cannot be subclassed; skipping writes is forbidden")

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: AuditRecord, **kwargs: object) -> None:
        if kwargs:
            raise TypeError("AuditLog.append does not accept skip flags")
        payload = {
            "timestamp": record.timestamp,
            "agent_id": record.agent_id,
            "event": record.event,
            "metrics": dict(record.metrics),
        }
        line = json.dumps(payload, sort_keys=True, default=_json_default) + "\n"
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError as exc:
            raise AuditError(f"failed to append validation audit to {self._path}") from exc


def write_event(
    *,
    path: Path,
    agent_id: str,
    event: str,
    metrics: Mapping[str, object],
    timestamp: str | None = None,
) -> None:
    """The only write helper. Always constructs an AuditLog and appends."""
    log = AuditLog(path)
    log.append(
        AuditRecord(
            timestamp=timestamp if timestamp is not None else utc_now_iso(),
            agent_id=agent_id,
            event=event,
            metrics=metrics,
        )
    )


def _json_default(value: object) -> str:
    return str(value)
