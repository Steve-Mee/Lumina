"""Shared adaptive intelligence snapshot helpers for REST and WebSocket surfaces."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_ADAPTIVE_TRANSITION_FIELDS = (
    "tier",
    "mode",
    "reasoning_mode",
    "degraded_state",
    "status_reason",
    "recommended_model",
    "recommended_provider",
    "context_length",
    "last_probe_error",
)


def resolve_adaptive_status_path(state_dir: Path | None = None) -> Path:
    raw = os.getenv("ADAPTIVE_INTELLIGENCE_STATUS_PATH", "").strip()
    if raw:
        return Path(raw)
    base = state_dir or Path("state")
    return base / "adaptive_intelligence_status.json"


def resolve_adaptive_history_path(state_dir: Path | None = None) -> Path:
    raw = os.getenv("ADAPTIVE_INTELLIGENCE_HISTORY_PATH", "").strip()
    if raw:
        return Path(raw)
    base = state_dir or Path("state")
    return base / "adaptive_intelligence_events.jsonl"


def load_adaptive_history_rows(
    *,
    history_path: Path,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if not history_path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with history_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
    except OSError:
        return []
    return rows[-max(1, int(limit)) :]


def build_adaptive_transition_summary(
    *,
    latest_record: dict[str, Any],
    previous_record: dict[str, Any] | None,
) -> dict[str, Any]:
    latest_payload = latest_record.get("payload", {})
    if not isinstance(latest_payload, dict):
        return {"is_transition": False, "changed_fields": []}
    previous_payload = previous_record.get("payload", {}) if isinstance(previous_record, dict) else {}
    if previous_record is None:
        return {
            "is_transition": False,
            "changed_fields": [],
            "from_state": {},
            "to_state": {k: latest_payload.get(k) for k in _ADAPTIVE_TRANSITION_FIELDS},
        }
    if not isinstance(previous_payload, dict):
        return {
            "is_transition": False,
            "changed_fields": [],
            "from_state": {},
            "to_state": {k: latest_payload.get(k) for k in _ADAPTIVE_TRANSITION_FIELDS},
        }
    changed = [
        k for k in _ADAPTIVE_TRANSITION_FIELDS if previous_payload.get(k) != latest_payload.get(k)
    ]
    return {
        "is_transition": bool(changed),
        "changed_fields": changed,
        "from_state": {k: previous_payload.get(k) for k in changed},
        "to_state": {k: latest_payload.get(k) for k in changed},
    }


def build_adaptive_intelligence_block(
    *,
    latest_record: dict[str, Any] | None,
    history_path: Path,
) -> dict[str, Any] | None:
    if not latest_record or not isinstance(latest_record, dict):
        return None

    payload = latest_record.get("payload")
    if not isinstance(payload, dict) or not payload.get("tier"):
        return None

    history_rows = load_adaptive_history_rows(history_path=history_path, limit=2)
    previous = history_rows[-2] if len(history_rows) >= 2 else None
    transition_summary = build_adaptive_transition_summary(
        latest_record=latest_record,
        previous_record=previous,
    )

    event_timestamp = latest_record.get("timestamp")
    if not isinstance(event_timestamp, str):
        event_timestamp = payload.get("timestamp")

    return {
        "status": payload,
        "transition_summary": transition_summary,
        "event_timestamp": event_timestamp,
    }
