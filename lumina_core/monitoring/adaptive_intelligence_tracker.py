from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from lumina_core.adaptive_intelligence import build_status_signature
from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas import AdaptiveIntelligenceState, typed_payload_from_event


class AdaptiveIntelligenceTracker:
    """Consumes adaptive intelligence events and persists latest + history."""

    TOPIC = "inference.adaptive_intelligence.state"

    def __init__(self, workspace_root: Path | str | None = None) -> None:
        self.workspace_root = Path(workspace_root).resolve() if workspace_root is not None else Path.cwd().resolve()
        self._lock = threading.RLock()
        self._latest_path = self.workspace_root / "state" / "adaptive_intelligence_status.json"
        self._history_path = self.workspace_root / "state" / "adaptive_intelligence_events.jsonl"
        self._subscription_token: str | None = None
        self._latest: dict[str, Any] | None = None

    def bind(self, event_bus: EventBus) -> None:
        with self._lock:
            if self._subscription_token is not None:
                return
            self._subscription_token = event_bus.subscribe(self.TOPIC, self._on_event)

    def _on_event(self, event: DomainEvent) -> None:
        state = typed_payload_from_event(event, AdaptiveIntelligenceState)
        record = {
            "topic": event.topic,
            "producer": event.producer,
            "timestamp": event.timestamp,
            "metadata": dict(event.metadata or {}),
            "payload": state.model_dump(mode="json", exclude_none=False),
        }
        self._persist(record)

    def _persist(self, record: dict[str, Any]) -> None:
        with self._lock:
            latest_payload = self._latest.get("payload", {}) if isinstance(self._latest, dict) else {}
            incoming_payload = record.get("payload", {})
            if isinstance(latest_payload, dict) and isinstance(incoming_payload, dict):
                if build_status_signature(latest_payload) == build_status_signature(incoming_payload):
                    # Keep latest timestamp/metadata fresh, but avoid history noise for identical state.
                    self._latest = record
                    self._latest_path.parent.mkdir(parents=True, exist_ok=True)
                    self._latest_path.write_text(json.dumps(record, ensure_ascii=True, indent=2), encoding="utf-8")
                    return
            self._latest = record
            self._latest_path.parent.mkdir(parents=True, exist_ok=True)
            self._latest_path.write_text(json.dumps(record, ensure_ascii=True, indent=2), encoding="utf-8")
            with self._history_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=True))
                fh.write("\n")

    def latest(self) -> dict[str, Any] | None:
        with self._lock:
            if self._latest is not None:
                return dict(self._latest)
        if not self._latest_path.exists():
            return None
        try:
            payload = json.loads(self._latest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def history(self, *, limit: int = 100) -> list[dict[str, Any]]:
        if not self._history_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        try:
            with self._history_path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        row = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(row, dict):
                        rows.append(row)
        except OSError:
            return []
        return rows[-max(1, int(limit)) :]
