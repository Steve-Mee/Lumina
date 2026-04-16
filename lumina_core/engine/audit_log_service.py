from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class AuditLogService:
    """Central append-only JSONL audit sink for trade decision transparency."""

    path: Path
    enabled: bool = True
    fail_closed_real: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _prev_hash: str = field(default="GENESIS")

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash = self._load_prev_hash()

    def _load_prev_hash(self) -> str:
        try:
            if not self.path.exists():
                return "GENESIS"
            tail = self.path.read_text(encoding="utf-8").splitlines()[-1:]
            if not tail:
                return "GENESIS"
            payload = json.loads(tail[0])
            return str(payload.get("hash") or "GENESIS")
        except Exception:
            return "GENESIS"

    @staticmethod
    def _validate_event(payload: dict[str, Any]) -> None:
        required = {"stage", "final_decision", "reason", "mode"}
        missing = [k for k in required if k not in payload]
        if missing:
            raise ValueError(f"Audit payload missing fields: {missing}")

    @staticmethod
    def _canonical_hash(payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def log_decision(self, payload: dict[str, Any], *, is_real_mode: bool = False) -> bool:
        if not self.enabled:
            return True

        event = dict(payload)
        event.setdefault("timestamp", _utc_iso())
        event.setdefault("schema_version", "trade_decision_audit_v1")

        try:
            self._validate_event(event)
            with self._lock:
                event["prev_hash"] = self._prev_hash
                event["hash"] = self._canonical_hash(event)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event, ensure_ascii=False) + "\n")
                self._prev_hash = str(event["hash"])
            return True
        except Exception:
            if self.fail_closed_real and bool(is_real_mode):
                return False
            return False
